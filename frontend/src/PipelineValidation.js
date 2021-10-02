import yaml from 'js-yaml'
import CodeMirror from 'codemirror'

CodeMirror.registerHelper("hint", "yaml", function (cm, options) {
    if (cm.options['filename'] != '/config.yml') {
        return null;
    }

    try {
      const sourceMap = yamlSourceMap(cm.getValue());
      const config = yaml.load(cm.getValue());
      const cur = cm.getCursor();
      let longest = null;
      for (const [key, pos] of Object.entries(sourceMap)) {
          if (cur.line >= pos.key.from.line && cur.line <= pos.value.to.line) {
              if (!longest || longest.length < key.length) {
                  longest = key;
              }
          }
      }

      if (longest !== null) {
          let parts = longest.split('.');
          while(parts.length) {
            if(cur.ch > sourceMap[parts.join('.')].key.from.ch) {
              break;
            }
            parts.pop();
          }
          longest = parts.join('.');

          const list = rules.hint(longest.split('.'), 0, config);
          const isKey = list.length && list[0].endsWith(': ');

          return {
              list: list,
              from: isKey ? cur : sourceMap[longest].value.from,
              to: isKey ? cur : sourceMap[longest].value.to,
          }
      }
    } catch(e) {
      if(e instanceof yaml.YAMLException) {
        console.log(e);
      } else {
        throw e;
      }
    }
});

function isObject(value) {
    return typeof value === 'object' && value !== null
}

function lineInfo(lineNumber, line) {
    const indentation = (line.match(/^\s*/) || [''])[0]
    return {
        from: { line: lineNumber, ch: indentation.length },
        to: { line: lineNumber, ch: line.length }
    }
}

function keyInfo(lineNumber, line, key) {
    const ch = line.indexOf(key)
    if (ch === -1) return lineInfo(lineNumber, line)
    return {
        from: { line: lineNumber, ch },
        to: { line: lineNumber, ch: ch + key.length }
    }
}

function valueInfo(lineNumber, line, value) {
    if (isObject(value)) return lineInfo(lineNumber, line)
    
    if(value === null) {
      const ch = line.indexOf(':')
      return {
          from: { line: lineNumber, ch: ch + 2 },
          to: { line: lineNumber, ch: ch + 2 }
      }
    }
    const asString = String(value)
    const ch = line.lastIndexOf(asString)
    if (ch === -1) return lineInfo(lineNumber, line)
    return {
        from: { line: lineNumber, ch },
        to: { line: lineNumber, ch: ch + asString.length }
    }
}

let prev = '';
function findNewPaths(paths, lines, value, path, lineNumber) {
    if (value === undefined) return
    const fullPath = path.join('.')
    if (fullPath && !paths[fullPath]) {
        const line = lines[lineNumber]
        const lastKey = path[path.length - 1]
        paths[fullPath] = {
            key: keyInfo(lineNumber, line, lastKey),
            value: valueInfo(lineNumber, line, value)
        }
        prev = fullPath;
    }
    if (typeof value !== 'object') return
    for (const key in value) {
        if (!value.hasOwnProperty(key)) continue
        findNewPaths(paths, lines, value[key], [...path, key], lineNumber)
    }
}

// sourcemap generation taken from github workflows
function yamlSourceMap(lines) {
    lines = lines.split("\n");
    const info = {
        from: { line: 0, ch: 0 },
        to: { line: lines.length - 1, ch: lines[lines.length - 1].lentth },
    };
    let paths = { '': { key: info, value: info } };
    for (let i = 0; i < lines.length; i++) {
        if (lines[i].trim().length == 0) {
            if (prev) {
                let x = [...prev.split('.')];
                x.pop();

                paths[x.join('.')].value.to.line = i;
            }
        }
        const partial = lines.slice(0, i + 1).join('\n')
        findNewPaths(paths, lines, yaml.load(partial), [], i)
    }

    for (let [path, info] of Object.entries(paths)) {
        path = path.split('.');
        path.pop();
        while (path.length) {
            paths[path.join('.')].value.to.line = Math.max(paths[path.join('.')].value.to.line, info.value.to.line);
            path.pop();
        }
    }

    return paths;
}

class DictRule {
    constructor(keys) {
        this.keys = keys;
    }

    validate(prefix, data, sourceMap) {
        if (data === null || data.constructor !== Object) {
            return [err(sourceMap[mkey(prefix)].value, "Not dictionary")];
        }

        let errors = [];
        for (const [key, value] of Object.entries(data)) {
            if (!(key in this.keys)) {
                errors.push(err(sourceMap[mkey(prefix, key)].key, `Unknown key ${key}`));
            } else {
                errors.push(...this.keys[key].validate(mkey(prefix, key), data[key], sourceMap));
            }
        }
        return errors;
    }

    hint(path, depth, data) {
        if (path == '' || depth >= path.length) {
            let alreadyUsed = data;
            for(const key of path) {
              alreadyUsed = alreadyUsed[key];
            }
            alreadyUsed = Object.keys(alreadyUsed || {});
            return Object.keys(this.keys).filter(k => alreadyUsed.indexOf(k) == -1).map(k => k + ': ');
        }

        if (path[depth] in this.keys) {
            return this.keys[path[depth]].hint(path, depth + 1, data);
        }
        return [];
    }
}

function mkey(...parts) {
    return parts.map(k => k.toString()).filter(k => k.length > 0).join('.');
}

class EnumRule {
    constructor(choices) {
        this.choices = choices;
    }
    validate(prefix, data, sourceMap) {
        if (data === null) {
            return [err(sourceMap[prefix].value, 'Missing value')];
        }

        if (this.choices.indexOf(data.toString()) < 0) {
            return [err(sourceMap[prefix].value, `Invalid value. Expected one of: ${this.choices.join(', ')}`)];
        }

        return [];
    }

    hint() {
        return this.choices;
    }
}

class UnionRule {
    constructor(...rules) {
        this.rules = rules;
    }

    validate(prefix, data, sourceMap) {
        let errors = [];
        for (const rule of this.rules) {
            const err = rule.validate(prefix, data, sourceMap);
            if (!err.length) {
                return [];
            }
            errors.push(...err);
        }


        let changed = true;
        let reduced = [];
        while (changed) {
            changed = false;
            for (const a of errors) {
                for (const b of errors) {
                    if (a.from.line >= b.from.line && a.to.line <= b.to.line && a.message != b.message) {
                        reduced.push(a);
                        changed = true;
                    }
                }
            }

            errors = reduced;
        }

        return reduced;
    }

    hint(path, depth, data) {
        let results = [];
        for (const rule of this.rules) {
            results.push(...rule.hint(path, depth, data));
        }
        return results;
    }

}

class ValueRule {
    validate(prefix, data, sourceMap) {
        if (data === null) {
            return [err(sourceMap[mkey(prefix)].value, "Should not be null.")];
        }
        if (data.constructor == Object) {
            return [err(sourceMap[mkey(prefix)].value, "Should not be dictionary.")];
        }

        return [];
    }

    hint() {
        return [];
    }
}

class PipelineRule {
    constructor(pipes) {
        this.pipes = pipes;
    }

    validate(prefix, data, sourceMap) {
        let errors = [];
        let i = 0;
        for (const pipe of data) {
            const type = pipe['type'];
            if (type in this.pipes) {
                delete pipe['type'];
                errors.push(...this.pipes[type].validate(`${prefix}.${i}`, pipe, sourceMap));
            } else {
                errors.push(err(sourceMap[mkey(prefix, i, 'type')].value, 'Unknown action'));
            }
            i++;
        }

        return errors;
    }

    hint(path, depth, data) {
        if (path.length == 3 && path[2] == 'type') {
            return Object.keys(this.pipes);
        }

        const pipeId = path[1];
        if(pipeId !== undefined) {
          const pipe = data['pipeline'][pipeId]['type'];

          return this.pipes[pipe].hint(path, depth + 1, data);
        }
        return []
    }
}

class ArrayRule {
    constructor(child) {
        this.child = child;
    }

    validate(prefix, data, sourceMap) {
        let i = 0;
        let errors = [];
        for (const item of data) {
            errors.push(...this.child.validate(mkey(prefix, i), data[i], sourceMap));
            i++;
        }
        return errors;
    }
    hint(path, depth, data) {
        return this.child.hint(path, depth + 1, data[path[depth]]);
    }

}

class PipeRule extends DictRule {
    constructor(keys) {
        super({
            ...keys,
            enabled: new EnumRule(['true', 'false', 'always', 'announce']),
            before: new ArrayRule(new ValueRule()),
            fail_on_error: new EnumRule(['true', 'false']),
        })
    }
}

class DockerPipeRule extends PipeRule {
    constructor(keys) {
        super({
            ...keys,
            limits: new DictRule({
              fsize: new ValueRule(),
              memory: new ValueRule(),
            }),
        })
    }
}

const rules = new DictRule({
    queue: new EnumRule(['evaluator', 'cuda']),
    timeout: new ValueRule(),
    tests: new ArrayRule(new DictRule({
        name: new ValueRule(),
        title: new ValueRule(),
        exit_code: new ValueRule(),
        args: new ArrayRule(new ValueRule()),
    })),
    pipeline: new PipelineRule({
        gcc: new DockerPipeRule({
            flags: new ValueRule(),
            output: new ValueRule(),
            ldflags: new ValueRule(),
            cmakeflags: new ValueRule(),
        }),
        run: new DockerPipeRule({
            commands: new ArrayRule(
                new UnionRule(
                    new DictRule({
                        cmd: new ValueRule(),
                        display: new ArrayRule(new ValueRule()),
                        hide: new EnumRule(['true', 'false']),
                        asciinema: new EnumRule(['true', 'false']),
                        timeout: new ValueRule(),
                    }),
                    new ValueRule()
                )
            )
        }),
        'flake8': new DockerPipeRule({
            select: new ArrayRule(new ValueRule()),
            ignore: new ArrayRule(new ValueRule()),
        }),
        'clang-tidy': new DockerPipeRule({
            checks: new ArrayRule(new ValueRule()),
            files: new ArrayRule(new ValueRule()),
        }),
        'tests': new DockerPipeRule({
            executable: new ValueRule(),
        }),
        'auto_grader': new PipeRule({
          propose: new EnumRule(['true', 'false']),
          overwrite: new EnumRule(['true', 'false']),
          after_deadline_multiplier: new ValueRule(),
        }),
    }),
});

function err(info, msg) {
    return {
        message: msg,
        from: CodeMirror.Pos(info.from.line, info.from.ch),
        to: CodeMirror.Pos(info.to.line, info.to.ch),
    }
}
export function lintPipeline(content) {
    try {
        const config = yaml.load(content);
        const sourceMap = yamlSourceMap(content);
        return rules.validate('', config, sourceMap);
    } catch (e) {
        if (e instanceof yaml.YAMLException) {
            const info = CodeMirror.Pos(e.mark.line, e.mark.column);
            return [{
                message: e.message,
                from: CodeMirror.Pos(e.mark.line, e.mark.column),
                to: CodeMirror.Pos(e.mark.line, e.mark.column + 1),
            }]
        } else {
            throw e;
        }
    }
}