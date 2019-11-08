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

def env_build(env):
    if not env:
        env = {}

    return " ".join([shlex.quote(f"-E{k}={v}") for k, v in env.items()])

class Test:
    def __init__(self, name):
        self.name = name
        self.stdin = None
        self.stdout = None
        self.exit_code = 0

class Evaluation:
    def __init__(self, source, sandbox):
        self.source = source
        self.sandbox = sandbox
        self.tests = self.load_tests()

    def load_tests(self):
        tests = []
        for out in glob.glob(os.path.join(self.source, '*.out')):
            test_name = os.path.basename(re.sub('.out$', '', out))

            t = Test(test_name)
            t.stdout = out

            stdin_path = os.path.join(self.source, f"{test_name}.in")
            if os.path.exists(stdin_path):
                t.stdin = stdin_path
            
            tests.append(t)
        return tests

    def task_file(self, path):
        return os.path.join(self.source, path)

    def evaluate(self, test: Test, args=None, env=None, name=None):
        args = {}
        if test.stdin:
            args['stdin'] = open(test.stdin, "r")
        
        p = subprocess.Popen(shlex.split(f"isolate -M /tmp/meta --processes=5 -s --run {env_build(env)} -- ./main"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, **args)
        p.wait()

        stdout = p.stdout.read().decode('utf-8')
        expected = open(test.stdout).read()

        meta = {}
        with open('/tmp/meta') as f:
            for line in f:
                key, val = line.split(':', 1)
                key = key.strip().replace('-', '')
                val = val.strip()

                if key != 'exitcode':
                    meta[key] = val

        return {**{
            'name': name if name else test.name,
            'stdout': stdout,
            'stderr': p.stderr.read().decode('utf-8'),
            'expected': expected,
            'exit_code': p.returncode,
            'success': stdout == expected
        }, **meta}



class Sandbox:
    def __init__(self):
        subprocess.check_call(["isolate", "--cleanup"])
        self.path = subprocess.check_output(["isolate", "--init", "--cg"]).decode('utf-8').strip()

    def system_path(self, path):
        return os.path.join(os.path.join(self.path, 'box'), path)

    def run(self, cmd, env=None):
        p = subprocess.Popen(shlex.split(f"isolate -s --run --processes=100 {env_build(env)} -e -- {cmd}"), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.wait() # TODO: may not work!

        return {
            'exit_code': p.returncode,
            'stdout': p.stdout.read().decode('utf-8'),
            'stderr': p.stderr.read().decode('utf-8'),
        }

    def open(self, path, mode='r'):
        return open(self.system_path(path), mode)

    def run_check(self, cmd):
        ret = self.run(cmd)
        if ret['exit_code'] != 0:
            raise "failed to execute:" + cmd
        return ret

    def compile(self, params = [], sources=None):
        if not sources:
            sources = [os.path.relpath(p, self.path + '/box') for p in glob.glob(self.system_path('*.c'))]
        # TODO: params formatting is not secure!
        return self.run("/usr/bin/gcc {} -o main -g {}".format(" ".join(sources), " ".join(params)))


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

    def run(self, evaluation):
        with evaluation.sandbox.open("__malloc.c", "w") as f:
            f.write(self.wrapper)

        gcc_result = evaluation.sandbox.compile(["-Wl,--wrap=malloc"])

        results = []
        for test in evaluation.tests:
            for i in range(10):
                env = {'__MALLOC_FAIL': i}
                results.append(evaluation.evaluate(test, env=env, name=f"{test.name} fails at malloc call #{i+1}"))

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
        ('test', InputGeneratorPipe())
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
