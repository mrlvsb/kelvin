import subprocess
from shutil import copyfile
import os
import glob
import shlex
import re
import tarfile
import json
import yaml
import tempfile
import random
import string

def env_build(env):
    if not env:
        env = {}

    return " ".join([shlex.quote(f"-E{k}={v}") for k, v in env.items()])

def rand_str(N):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=N))

def apply_filters(s, filters):
    for f in filters:
        s = f.filter(s)
    return s

def compare(actual, expected, filters):
    return apply_filters(actual, filters) == apply_filters(expected, filters)


class LowerFilter:
    def filter(self, s):
        return s.lower()

class TrailingSpacesFilter:
    def filter(self, s):
        s = re.sub('^\s+', '', s)
        s = re.sub('\s+$', '', s)
        return s

class AllSpacesFilter:
    def filter(self, s):
        s = re.sub('\s+', ' ', s, re.MULTILINE)
        return s.strip()

class TempFile:
    def __init__(self, suffix, dir):
        self.suffix = suffix
        self.dir = dir
        self.path = None
        self.fd = None

    def __enter__(self):
        self.path = os.path.join(self.dir, f'{rand_str(5)}_{self.suffix}')
        self.fd = open(self.path, 'w+')
        return self.fd

    def __exit__(self, type, value, traceback):
        self.fd.close()
        os.remove(self.path)



class Test:
    def __init__(self, name):
        self.name = name
        self.stdin = None
        self.stdout = None
        self.stderr = None
        self.args = []
        self.exit_code = 0
        self.files = []
        self.check = None
        self.filters = []

class Evaluation:
    def __init__(self, source, sandbox):
        self.source = source
        self.sandbox = sandbox
        self.tests = self.load_tests()

    def load_tests(self):
        tests = {}

        def create_test(name):
            if name in tests:
                return tests[name]

            t = Test(name)

            path = os.path.join(self.source, f"{name}.out")
            if os.path.exists(path):
                t.stdout = path

            path = os.path.join(self.source, f"{name}.err")
            if os.path.exists(path):
                t.stderr = path

            stdin_path = os.path.join(self.source, f"{name}.in")
            if os.path.exists(stdin_path):
                t.stdin = stdin_path
                

            tests[name] = t
            return t

        for ext in ['out', 'err']:
            for out in glob.glob(os.path.join(self.source, f"*.{ext}")):
                test_name = os.path.basename(re.sub(f".{ext}$", '', out))
                create_test(test_name)

        try:
            with open(os.path.join(self.source, 'config.yml')) as f:
                conf = yaml.load(f.read(), Loader=yaml.SafeLoader)
                if conf:
                    filters = []
                    for f in conf.get('filters', []):
                        n = f"{f}Filter"
                        filters.append(globals()[n]())

                    for test_conf in conf.get('tests', []):
                        t = create_test(test_conf.get('name', f'test {len(tests)}'))
                        t.exit_code = test_conf.get('exit_code', 0)
                        t.args = test_conf.get('args', [])
                        t.files = test_conf.get('files', [])
                        t.filters += filters

                    for k, t in tests.items():
                        t.filters = filters + t.filters
        except FileNotFoundError:
            pass

        return tests.values()

    def task_file(self, path):
        return os.path.join(self.source, path)

    def evaluate(self, test: Test, args=None, env=None, name=None):
        args = {}
        stdin = ""
        if test.stdin:
            args['stdin'] = open(test.stdin, "r")
            stdin = args['stdin'].read()
            args['stdin'].seek(0)

        cmd = ['./main'] + test.args
        p = subprocess.Popen(shlex.split(f"isolate -M /tmp/meta --processes=5 -s --run {env_build(env)} --") + cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **args)
        p.wait()

        if test.stdin:
            args['stdin'].close()

        stdout = p.stdout.read().decode('utf-8')
        stderr = p.stderr.read().decode('utf-8')

        p.stdout.close()
        p.stderr.close()

        success = True
        expected = ""
        if test.stdout:
            with open(test.stdout) as f:
                expected = f.read()
            success &= compare(stdout, expected, test.filters)

        if test.stderr:
            with open(test.stderr) as f:
                expected = f.read()
            success &= compare(stderr, expected, test.filters)

        files = []
        for f in test.files:
            with self.sandbox.open(f['path']) as cur, open(os.path.join(self.source, f['expected'])) as exp:
                content = cur.read()
                expected = exp.read()
                same = compare(content, expected, test.filters)

                files.append({
                    'path': f['path'],
                    'content': content,
                    'expected': expected,
                    'success': same,
                })

                success &= same


        meta = {}
        with open('/tmp/meta') as f:
            for line in f:
                key, val = line.split(':', 1)
                key = key.strip().replace('-', '')
                val = val.strip()

                if key == 'exitcode':
                    meta['exit_code'] = int(val)
                else:
                    meta[key] = val

        cmd_txt = ' '.join(cmd)
        if test.stdin:
            cmd_txt += f' < {shlex.quote(os.path.basename(test.stdin))}'

        return {**{
            'name': name if name else test.name,
            'stdout': stdout,
            'stderr': stderr,
            'stdin': stdin,
            'expected': expected,
            'success': success,
            'files': files,
            'command': cmd_txt,
        }, **meta}



class Sandbox:
    def __init__(self):
        subprocess.check_call(["isolate", "--cleanup"])
        self.path = subprocess.check_output(["isolate", "--init", "--cg"]).decode('utf-8').strip()

    def system_path(self, path=''):
        return os.path.join(os.path.join(self.path, 'box'), path)

    def run(self, cmd, env=None):
        p = subprocess.Popen(shlex.split(f"isolate -s --run --processes=100 {env_build(env)} -e -- {cmd}"), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.wait() # TODO: may not work!

        res = {
            'exit_code': p.returncode,
            'stdout': p.stdout.read().decode('utf-8'),
            'stderr': p.stderr.read().decode('utf-8'),
        }

        p.stdout.close()
        p.stderr.close()

        return res

    def open(self, path, mode='r'):
        return open(self.system_path(path), mode)

    def open_temporary(self, suffix):
        return TempFile(suffix, self.system_path())

    def copy(self, local, box):
        copyfile(local, self.system_path(box))

    def run_check(self, cmd):
        ret = self.run(cmd)
        if ret['exit_code'] != 0:
            raise "failed to execute:" + cmd
        return ret

    def compile(self, flags = None, sources=None):
        if not sources:
            sources = [os.path.relpath(p, self.path + '/box') for p in glob.glob(self.system_path('*.c'))]

        if not flags:
            flags = []
        flags = ['-g', '-lm', '-Wall', '-pedantic'] + flags
        
        command = '/usr/bin/gcc {sources} -o main {flags}'.format(
            sources=' '.join(map(shlex.quote, sources)),
            flags=' '.join(map(shlex.quote, flags))
        ).strip()

        result = self.run(command)
        result['command'] = command
        return result

class GccPipeline:
    def __init__(self, gcc_params=[]):
        self.gcc_params = gcc_params

    def run(self, evaluation):
        # TODO: params formatting is not secure!
        gcc_result = evaluation.sandbox.compile(self.gcc_params)

        results = []
        for test in evaluation.tests:
            results.append(evaluation.evaluate(test))
           
        return {
            "gcc": gcc_result,
            "tests": results,
        }

class Mallocer:
    wrapper = """
#include <stdio.h>
#include <memory.h>
#include <stdlib.h>

static int failed;
static int fail_at = -1;

void *__real_malloc(size_t size);
void* __wrap_malloc (size_t c) {
  if(fail_at == -1) {
    char *env = getenv("__MALLOC_FAIL");
    if(env) {
      fail_at = atoi(env);
    }
  }

  if(failed >= fail_at) {
    return NULL;
  }
  failed++;

  return __real_malloc (c);
}
    """

    def __init__(self, max_fails=10):
        self.max_fails = max_fails

    def run(self, evaluation):
        with evaluation.sandbox.open_temporary("malloc.c") as f:
            f.write(self.wrapper)
            f.close()

            gcc_result = evaluation.sandbox.compile(["-Wl,--wrap=malloc"])

            results = []
            for test in evaluation.tests:
                for i in range(self.max_fails):
                    env = {'__MALLOC_FAIL': i}
                    result = evaluation.evaluate(test, env=env, name=f"{test.name} fails at malloc call #{i+1}")
                    results.append(result)

                    if result['success']:
                        break

            return {
                "gcc": gcc_result,
                "tests": results,
            }
        
class DownloadPipe:
    def run(self, evaluation):
        src = 'submit'
        if tarfile.is_tarfile(evaluation.sandbox.system_path(src)):
            evaluation.sandbox.run_check('tar -xf {}'.format(src))
        else:
            evaluation.sandbox.run_check('/bin/mv {} main.c'.format(src))

class InputGeneratorPipe:
    def __init__(self, path='input_generator.py', count=4):
        self.gen_path = path
        self.count = count


    def run(self, evaluation):
        gcc_result = evaluation.sandbox.compile(['-fsanitize=address'])
        path = evaluation.task_file('input_generator.py')

        results = []
        for i in range(self.count):
            with tempfile.NamedTemporaryFile() as stdin, tempfile.NamedTemporaryFile() as stdout:
                p = subprocess.Popen(["python3", path], stdout=stdin)
                p.wait()

                stdin.seek(0)

                p = subprocess.Popen([evaluation.task_file('solution')], stdin=stdin, stdout=stdout)
                p.wait()

                test = Test(f"random {i}")
                test.stdin = stdin.name
                test.stdout = stdout.name
                results.append(evaluation.evaluate(test))
            
        
        return {
            'gcc': gcc_result,
            'tests': results,
        }

def evaluate(task_dir, submit_path):
    sandbox = Sandbox()
    evaluation = Evaluation(task_dir, sandbox)

    copyfile(submit_path, os.path.join(sandbox.path, "box/submit"))

    pipeline = [
        ('download', DownloadPipe()),
        ('normal run', GccPipeline()),
        ('run with sanitizer', GccPipeline(['-fsanitize=address', '-fsanitize=bounds', '-fsanitize=undefined'])),
        ('malloc fail tester', Mallocer()),
        ('random inputs', InputGeneratorPipe())
    ]
    
    result = []
    for name, pipe in pipeline:
        res = pipe.run(evaluation)
        if res:
            result.append({'name': name, **res})

    return result




if __name__ == "__main__":
    import sys
    sandbox = Sandbox()
    evaluation = Evaluation(sys.argv[1], sandbox)

    copyfile(sys.argv[2], os.path.join(sandbox.path, "box/submit"))

    pipeline = [
        ('download', DownloadPipe()),
        #('normal run', GccPipeline()),
        #('run with sanitizer', GccPipeline(['-fsanitize=address', '-fsanitize=bounds', '-fsanitize=undefined'])),
        #('malloc fail tester', Mallocer()),
        ('test', InputGeneratorPipe())
    ]
    
    result = []
    for name, pipe in pipeline:
        res = pipe.run(evaluation)
        if res:
            result.append({'name': name, **res})
    from pprint import pprint
    #pprint(result)


    for pipe in result:
        print("====================================================")
        print(pipe['name'].upper())
        print("====================================================")
        print(pipe['gcc']['stderr'])

        for test in pipe['tests']:
            print("[{}] {}".format('OK' if test['success'] else 'ERR', test['name']))
            print(test['stdout'])
            print(test['stderr'])
            print(test['expected'])
        
    #x = yaml.load(open("tasks/hello_world/config.yml").read(), Loader=yaml.SafeLoader)
    #print(x)
