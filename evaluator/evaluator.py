import subprocess
from shutil import copyfile
import sys
import os
import io
import glob
import shlex
import shutil
import re
import json
import tempfile
import random
import string
import logging

from . import filters
from . import pipelines
from . import testsets
from .results import EvaluationResult, TestResult
from .comparators import text_compare, binary_compare

logger = logging.getLogger("evaluator")

def env_build(env):
    if not env:
        env = {}

    return " ".join([shlex.quote(f"-E{k}={v}") for k, v in env.items()])

def rand_str(N):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=N))


def compare(actual, expected, used_filters):
    return filters.apply_filters(actual, used_filters) == filters.apply_filters(expected, used_filters)

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

class Evaluation:
    def __init__(self, task_path : str, result_path: str, sandbox, meta=None):
        self.sandbox = sandbox
        self.task_path = task_path
        self.result_path = result_path
        self.tests = testsets.TestSet(task_path, meta)

        try:
            shutil.rmtree(result_path)
        except FileNotFoundError:
            pass
        
        os.makedirs(result_path)

    def task_file(self, path):
        return os.path.join(self.task_path, path)

    def run(self):
        pipeline = [
            ('download', pipelines.DownloadPipe()),
            ('normal run', pipelines.GccPipeline()),
            ('run with sanitizer', pipelines.GccPipeline(['-fsanitize=address', '-fsanitize=bounds', '-fsanitize=undefined'])),
            #('malloc fail tester', Mallocer()),
            #('random inputs', InputGeneratorPipe())
        ]
        
        result = EvaluationResult(self.result_path)
        for name, pipe in pipeline:
            logger.info(f"executing {name}")
            res = pipe.run(self)
            if res:
                res['name'] = name
                result.pipelines.append(res)

        result.save(os.path.join(self.result_path, 'result.json'))
        return result

    def evaluate(self, test: testsets.Test, env=None, title=None):
        filters = self.tests.filters + test.filters

        result = TestResult(test.name, self.result_path)
        result.title = title if title else test.title

        args = {}
        if test.stdin:
            args['stdin'] = test.stdin.open()
            result.copy_result_file('stdin', actual=test.stdin)

        # run process in the sandbox
        cmd = ['./main'] + test.args
        flags = " ".join([shlex.quote(f"--{k}={v}") for k, v in self.tests.limits.items()])
        stdout_name = rand_str(10)
        stderr_name = rand_str(10)
        isolate_cmd = shlex.split(f"isolate -M /tmp/meta --cg {flags} -o {stdout_name} -r {stderr_name} -s --run {env_build(env)} --") + cmd
        logger.debug("executing in isolation: %s", shlex.join(isolate_cmd))
        p = subprocess.Popen(isolate_cmd, **args)
        p.communicate()

        if test.stdin:
            args['stdin'].close()
        
        # copy all result and expected files
        result.copy_result_file('stdout', actual=self.sandbox.system_path(stdout_name), expected=test.stdout)
        result.copy_result_file('stderr', actual=self.sandbox.system_path(stderr_name), expected=test.stderr)
        for f in test.files:
            result.copy_result_file(f['path'], actual=self.sandbox.system_path(f['path']), expected=f['expected'])
        
        # do a comparsion
        for name, opts in result.files.items():
            if 'expected' not in opts:
                continue

            if 'actual' not in opts:
                opts['error'] = 'file not found'
                result['success'] &= False
                continue

            comparator = text_compare
            comparator_args = {'filters': filters}
            if name in self.tests.comparators:
                all_comparators = {
                    'binary': binary_compare
                }

                comparator = all_comparators[self.tests.comparators[name]['type']]
                comparator_args = {}
        
            success, output = comparator(opts['expected'].path, opts['actual'].path, **comparator_args)
            result['success'] &= success

        # extract statistics
        with open('/tmp/meta') as f:
            for line in f:
                key, val = line.split(':', 1)
                key = key.strip().replace('-', '')
                val = val.strip()

                if key == 'exitcode':
                    result['exit_code'] = int(val)
                else:
                    result[key] = val

        result['success'] &= test.exit_code == result['exit_code']

        # save issued commandline
        result['command'] = ' '.join(cmd)
        if test.stdin:
            result['command'] += f' < {shlex.quote(os.path.basename(test.stdin.path))}'

        # run custom evaluation script
        if test.script:
            check = getattr(test.script, 'check', None)
            if check:
                result['success'] &= check(result, self)

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

def evaluate(task_path, submit_path, result_path, meta=None):
    '''
    Called by Django.
    '''

    sandbox = Sandbox()
    evaluation = Evaluation(task_path, result_path, sandbox, meta)

    logger.info(f"evaluating {submit_path}")
    copyfile(submit_path, os.path.join(sandbox.path, "box/submit"))

    return evaluation.run()

if __name__ == "__main__":
    import argparse
    from pprint import pprint
    import shutil

    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument('task_dir', help='path to directory with the task')
    parser.add_argument('solution', help='path to source code in .c or tar')
    parser.add_argument('--print-json')

    args = parser.parse_args()
    result = evaluate(args.task_dir, args.solution, '/tmp/eval')

    if args.print_json:
        pprint(result)