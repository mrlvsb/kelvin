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
          const isKey = list.length && (list[0].constructor == Object ? list[0].text.endsWith(': ') : list[0].endsWith(': '));

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

function getRule(record) {
    return Array.isArray(record) ? record[0] : record;
}

function renderHelpFn(el, self, data) {
    const header = document.createElement('strong');
    header.innerText = data['text'];
    el.appendChild(header);
    if(data['help']) {
        const x = document.createElement("div");
        x.innerHTML = data['help'];
        el.appendChild(x);
    }
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
                const rule = getRule(this.keys[key]);
                errors.push(...rule.validate(mkey(prefix, key), data[key], sourceMap));
            }
        }
        return errors;
    }

    hint(path, depth, data) {
        if (path == '' || depth >= path.length) {
            let alreadyUsed = data;
            for(const key of path) {
                if(alreadyUsed[key]) {
                    alreadyUsed = alreadyUsed[key];
                }
            }
            alreadyUsed = Object.keys(alreadyUsed || {});

            return Object.keys(this.keys).filter(k => alreadyUsed.indexOf(k) == -1).map(k => {
                return {
                    text: k + ': ',
                    help: Array.isArray(this.keys[k]) ? this.keys[k][1] : null,
                    render: renderHelpFn,
                }
            });
        }

        if (path[depth] in this.keys) {
            const rule = getRule(this.keys[path[depth]]);
            return rule.hint(path, depth + 1, data);
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
        if(!Array.isArray(data)) {
          return [err(sourceMap[mkey(prefix)].key, "Pipeline must be array")];
        }

        let errors = [];
        let i = 0;
        for (const pipe of data) {
            if(!pipe || pipe.constructor !== Object || !('type' in pipe)) {
              return [err(sourceMap[mkey(prefix, i)].key, "Action must contain type")];
            }
            const type = pipe['type'];
            if (type in this.pipes) {
                delete pipe['type'];
                const rule = getRule(this.pipes[type]);
                errors.push(...rule.validate(`${prefix}.${i}`, pipe, sourceMap));
            } else {
                errors.push(err(sourceMap[mkey(prefix, i, 'type')].value, 'Unknown action'));
            }
            i++;
        }

        return errors;
    }

    hint(path, depth, data) {
        if (path.length == 3 && path[2] == 'type') {
            return Object.keys(this.pipes).map(k => {
                return {
                    text: k,
                    help: Array.isArray(this.pipes[k]) ? this.pipes[k][1] : null,
                    render: renderHelpFn,
                }
            });
        }

        const pipeId = path[1];
        if(pipeId !== undefined) {
          const pipe = data['pipeline'][pipeId];
          if(pipe && pipe['type']) {
            return getRule(this.pipes[pipe]).hint(path, depth + 1, data);
          } else {
              return ['type: '];
          }
        }
        return []
    }
}

class ArrayRule {
    constructor(child) {
        this.child = child;
    }

    validate(prefix, data, sourceMap) {
        if(!Array.isArray(data)) {
            return [err(sourceMap[mkey(prefix)].key, 'Should be array.')]
        }
        
        let i = 0;
        let errors = [];
        for (const item of data) {
            errors.push(...this.child.validate(mkey(prefix, i), data[i], sourceMap));
            i++;
        }
        return errors;
    }
    hint(path, depth, data) {
        return this.child.hint(path, depth + 1, data);
    }

}

class PipeRule extends DictRule {
    constructor(keys) {
        super({
            ...keys,
            enabled: new EnumRule(['true', 'false', 'always', 'announce']),
            fail_on_error: [new EnumRule(['true', 'false']), 'Stop execution of successive actions if this action fails'],
        })
    }
}

class DockerPipeRule extends PipeRule {
    constructor(keys) {
        super({
            ...keys,
            before: [new ArrayRule(new ValueRule()), 'List of commands for container preparation. Will be cached for next run.'],
            limits: new DictRule({
              fsize: [new ValueRule(), 'Maximal size for one created file. You can use suffixes like 16M'],
              memory: [new ValueRule(), 'Maximal memory use for the container, not the process. You can use suffixes like 128M'],
            }),
        })
    }
}

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

const rules = new DictRule({
    queue: [new EnumRule(['evaluator', 'cuda']), "Queue where to execute the job"],
    timeout: [new ValueRule(), "Maximal execution of the pipeline in seconds. You can also use <strong>15m</strong> or <strong>1h</strong>."],
    tests: new ArrayRule(new DictRule({
        name: [new ValueRule(), 'The identification of test. Should not contain any space.'],
        title: [new ValueRule(), 'Human readable title of the test.'],
        exit_code: [new ValueRule(), 'Expected exit code from the process. By default <strong>0</strong>'],
        args: [new ArrayRule(new ValueRule()), 'Array of arguments passed to the program'],
    })),
    pipeline: new PipelineRule({
        gcc: [new DockerPipeRule({
            flags: [new ValueRule(), 'Flags for the gcc/g++ compiler.'],
            output: [new ValueRule(), 'Built executable name <strong>-o main</strong>'],
            ldflags: new ValueRule(),
            cmakeflags: new ValueRule(),
        }), 'Build program with CMake, make or collect all files and compile them directly with <strong>gcc</strong> or <strong>g++</strong>'],
        run: [new DockerPipeRule({
            commands: [new ArrayRule(
                new UnionRule(
                    new DictRule({
                        cmd: new ValueRule(),
                        display: [new ArrayRule(new ValueRule()), 'List of image/video patterns that will be converted and shown on the result page.'],
                        hide: [new EnumRule(['true', 'false']), 'Hide command and its output from the result page.'],
                        asciinema: [new EnumRule(['true', 'false']), 'Run the command in asciinema and generate video animation from the run.'],
                        timeout: [new ValueRule(), 'Timeout in seconds. You can also suffixes like 5m'],
                    }),
                    new ValueRule()
                )
            ), 'Command can be string or a dict.<br>Commands prefixed with <strong>#</strong> are not shown on the result page.']
        }), 'Run custom commands and show the output.'],
        'flake8': new DockerPipeRule({
            select: [new ArrayRule(new ValueRule()), 'List of enabled PEP8 codes. Can be array or string delimited by comma'],
            ignore: [new ArrayRule(new ValueRule()), 'List of ignored PEP8 codes. Can be array or string delimited by comma'],
        }),
        'clang-tidy': new DockerPipeRule({
            checks: [new ArrayRule(new ValueRule()), 'List of used <a href="https://clang.llvm.org/extra/clang-tidy/checks/list.html">checks</a>. You may use asterisks <strong>*</strong> or block checks with hyphen <strong>-</strong>.'],
            files: [new ArrayRule(new ValueRule()), 'List of analyzed files.'],
        }),
        'tests': new DockerPipeRule({
            executable: new ValueRule(),
        }),
        'auto_grader': new PipeRule({
          propose: [new EnumRule(['true', 'false']), 'Only propose points without assigning.'],
          overwrite: [new EnumRule(['true', 'false']), 'Do not overwrite already assigned points in current submit.'],
          after_deadline_multiplier: [new ValueRule(), 'Points multiplier in range of 0 to 1 when submit is after deadline'],
        }),
    }),
});
