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
import logging

logger = logging.getLogger("evaluator")

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
        s = re.sub(r'^\s+', '', s, flags=re.MULTILINE)
        s = re.sub(r'\s+$', '', s, flags=re.MULTILINE)
        return s

class AllSpacesFilter:
    def filter(self, s):
        s = re.sub(r'\s+', ' ', s, flags=re.MULTILINE)
        return s.strip()

class StripFilter:
    def filter(self, s):
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

class File:
    def __init__(self, path):
        self.path = path

    def open(self, mode='r'):
        return open(self.path)

    def read(self):
        with self.open() as f:
            return f.read()


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
        self.limits = {}
        self._title = None

    @property
    def escaped_args(self):
        return " ".join(map(shlex.quote, self.args))

    @property
    def title(self):
        return self._title if self._title else self.name
    
    @title.setter
    def title(self, value):
        self._title = value


class Evaluation:
    def __init__(self, source, sandbox):
        self.source = source
        self.sandbox = sandbox
        self.filters = []
        self.limits = {
            'wall-time': 0.5,
            'time': 0,
            'processes': 10,
            'stack': 0,
            'cg-mem': 5 * 1024 * 1024,
            'fsize': 1024 * 1024,
        }
        self.tests = self.load_tests()

    def load_tests(self):
        tests = {}

        def create_test(name):
            if name in tests:
                return tests[name]

            t = Test(name)

            path = os.path.join(self.source, f"{name}.out")
            if os.path.exists(path):
                t.stdout = File(path)

            path = os.path.join(self.source, f"{name}.err")
            if os.path.exists(path):
                t.stderr = File(path)

            stdin_path = os.path.join(self.source, f"{name}.in")
            if os.path.exists(stdin_path):
                t.stdin = File(stdin_path)
                

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
                    for f in conf.get('filters', []):
                        n = f"{f}Filter"
                        self.filters.append(globals()[n]())

                    for k, v in conf.get('limits', {}).items():
                        if k not in self.limits:
                            logging.error(f'unknown limit {k}')
                        else:
                            self.limits[k] = v


                    for test_conf in conf.get('tests', []):
                        t = create_test(str(test_conf.get('name', f'test {len(tests)}')))
                        t.title = test_conf.get('title', t.name)
                        t.exit_code = test_conf.get('exit_code', 0)
                        t.args = [str(s) for s in test_conf.get('args', [])]
                        files = test_conf.get('files', [])
                        for f in files:
                            t.files.append({
                                'path': f['path'],
                                'expected': File(os.path.join(self.source, f['expected'])),
                            })

        except FileNotFoundError:
            pass

        return tests.values()

    def task_file(self, path):
        return os.path.join(self.source, path)

    def evaluate(self, test: Test, env=None, title=None):
        result = {
             'name': test.name,
             'title': title if title else test.title,
             'success': True,
             'fail_reason': [],
        }

        args = {}
        if test.stdin:
            args['stdin'] = test.stdin.open()
            result['stdin'] = args['stdin'].read()
            args['stdin'].seek(0)

        cmd = ['./main'] + test.args
        flags = " ".join([shlex.quote(f"--{k}={v}") for k, v in self.limits.items()])
        p = subprocess.Popen(shlex.split(f"isolate -M /tmp/meta --cg {flags} -s --run {env_build(env)} --") + cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **args)
        result['stdout'], result['stderr'] = p.communicate()

        if test.stdin:
            args['stdin'].close()

        result['exit_code'] = p.returncode
        result['stdout'] = result['stdout'].decode('utf-8')
        result['stderr'] = result['stderr'].decode('utf-8')

        p.stdout.close()
        p.stderr.close()

        filters = self.filters + test.filters

        if test.stdout:
            with test.stdout.open() as f:
                result['stdout_expected'] = f.read()
            success = compare(result['stdout'], result['stdout_expected'], filters)
            result['success'] &= success
            if not success:
                result['fail_reason'].append('stdout not matches')

        if test.stderr:
            with test.stderr.open() as f:
                result['stderr_expected'] = f.read()
            success = compare(result['stderr'], result['stderr_expected'], filters)
            result['success'] &= success
            if not success:
                result['fail_reason'].append('stderr not matches')

        result['files'] = []
        for f in test.files:
            try:
                with self.sandbox.open(f['path']) as cur:
                    content = cur.read()
                    expected = f['expected'].read()
                    same = compare(content, expected, filters)

                    result['files'].append({
                        'path': f['path'],
                        'content': content,
                        'expected': expected,
                        'success': same,
                    })

                    result['success'] &= same
            except FileNotFoundError as e:
                result['files'].append({
                    'path': f['path'],
                    'expected': f['expected'].read(),
                    'success': False,
                    'error': 'file not found',
                })

                result['success'] &= False



        with open('/tmp/meta') as f:
            for line in f:
                key, val = line.split(':', 1)
                key = key.strip().replace('-', '')
                val = val.strip()

                if key == 'exitcode':
                    result['exit_code'] = int(val)
                else:
                    result[key] = val

        result['command'] = ' '.join(cmd)
        if test.stdin:
            result['command'] += f' < {shlex.quote(os.path.basename(test.stdin.path))}'

        return result

class Sandbox:
    def __init__(self):
        subprocess.check_call(["isolate", "--cleanup"])
        self.path = subprocess.check_output(["isolate", "--init", "--cg"]).decode('utf-8').strip()

    def system_path(self, path=''):
        return os.path.join(os.path.join(self.path, 'box'), path)

    def run(self, cmd, env=None):
        isolation_cmd = f"isolate -s --run --processes=100 {env_build(env)} -e -- {cmd}"
        logger.info(f"executing in isolation: {isolation_cmd}")

        p = subprocess.Popen(shlex.split(isolation_cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()

        res = {
            'exit_code': p.returncode,
            'stdout': stdout.decode('utf-8'),
            'stderr': stderr.decode('utf-8'),
        }
        logger.info(f"exit_code: {p.returncode}")

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

            gcc_result = evaluation.sandbox.compile(["-Wl,--wrap=malloc", '-fsanitize=address'])

            results = []
            for test in evaluation.tests:
                for i in range(self.max_fails):
                    env = {'__MALLOC_FAIL': i}
                    result = evaluation.evaluate(test, env=env, title=f"{test.name} fails at malloc call #{i+1}")
                    if not result['success']:
                        # TODO: detect kill from sanitizer
                        result['success'] = result['exit_code'] != 0 and 'AddressSanitizer' not in result['stderr']

                    results.append(result)

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
        path = evaluation.task_file(self.gen_path)

        if not os.path.exists(path):
            return

        results = []
        for i in range(self.count):
            with tempfile.NamedTemporaryFile() as stdin, tempfile.NamedTemporaryFile() as stdout, tempfile.NamedTemporaryFile() as stderr:
                p = subprocess.Popen(["python3", path], stdout=stdin)
                p.wait()

                stdin.seek(0)

                p = subprocess.Popen([evaluation.task_file('solution')], stdin=stdin, stdout=stdout, stderr=stderr)
                p.wait()

                test = Test(f"random {i}")
                test.stdin = stdin.name
                test.stdout = stdout.name
                test.stderr = stderr.name
                results.append(evaluation.evaluate(test))
            
        
        return {
            'gcc': gcc_result,
            'tests': results,
        }

def evaluate(task_dir, submit_path):
    sandbox = Sandbox()
    evaluation = Evaluation(task_dir, sandbox)

    logger.info(f"evaluating {submit_path}")
    copyfile(submit_path, os.path.join(sandbox.path, "box/submit"))

    pipeline = [
        ('download', DownloadPipe()),
        ('normal run', GccPipeline()),
        ('run with sanitizer', GccPipeline(['-fsanitize=address', '-fsanitize=bounds', '-fsanitize=undefined'])),
        #('malloc fail tester', Mallocer()),
        #('random inputs', InputGeneratorPipe())
    ]
    
    result = []
    for name, pipe in pipeline:
        logger.info(f"executing {name}")
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
