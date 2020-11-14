import subprocess
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
from .comparators import text_compare, binary_compare, image_compare
from .utils import copyfile
from kelvin.settings import BASE_DIR

from rq import get_current_job

logger = logging.getLogger("evaluator")

def env_build(env):
    if not env:
        env = {}

    return ['-E' + shlex.quote(f"{k}={v}") for k, v in env.items()]

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
        self.result_path = os.path.join(BASE_DIR, result_path)
        self.result = None
        self.tests = testsets.TestSet(task_path, meta)

        try:
            shutil.rmtree(result_path)
        except FileNotFoundError:
            pass
        
        os.makedirs(result_path)

    def task_file(self, path):
        return os.path.join(self.task_path, path)

    def run(self):
        job = get_current_job()
        job.meta['actions'] = len(self.tests.pipeline)
        job.meta['current_action'] = 0
        job.save_meta()

        self.result = EvaluationResult(self.result_path)
        for pipe in self.tests.pipeline:
            logger.info(f"executing {pipe.id}")
            res = pipe.run(self)
            if res:
                res['id'] = pipe.id
                res['title'] = pipe.title
                self.result.pipelines.append(res)

                if 'failed' in res and res['failed']:
                    break

            job.meta['current_action'] += 1
            job.save_meta()

        self.result.save(os.path.join(self.result_path, 'result.json'))
        return self.result

    def evaluate(self, runner, test: testsets.Test, executable, env=None, title=None):
        filters = self.tests.filters + test.filters

        result_dir = os.path.join(self.result_path, runner)
        try:
            os.makedirs(result_dir)
        except FileExistsError:
            pass
        result = TestResult(result_dir, {'name': test.name})
        result.title = title if title else test.title

        # copy input files to the sandbox
        for path, f in test.files.items():
            if f.input:
                copyfile(f.path, self.sandbox.system_path(path))

        args = {}
        if test.stdin:
            args['stdin'] = test.stdin.open()
            result.copy_result_file('stdin', actual=test.stdin.file.path)

        # run process in the sandbox
        cmd = [executable] + test.args
        flags = " ".join([shlex.quote(f"--{k}={v}") for k, v in self.tests.limits.items()])
        stdout_name = rand_str(10)
        stderr_name = rand_str(10)
        isolate_cmd = shlex.split(f"isolate -M /tmp/meta --cg {flags} -o {stdout_name} -r {stderr_name} -s --run {' '.join(env_build(env))} --") + cmd
        logger.debug("executing in isolation: %s", " ".join((isolate_cmd))) # TODO: shlex.join only in python3.8
        p = subprocess.Popen(isolate_cmd, **args)
        p.communicate()

        if test.stdin:
            args['stdin'].close()
        
        # copy all result and expected files
        result.copy_result_file('stdout', actual=self.sandbox.system_path(stdout_name), expected=test.stdout, force_save=True)
        result.copy_result_file('stderr', actual=self.sandbox.system_path(stderr_name), expected=test.stderr)
        for path, expected in test.files.items():
            if path in ['stdout', 'stderr']:
                continue

            if expected.input:
                result.copy_input_file(path, expected)
            else:
                result.copy_result_file(path, actual=self.sandbox.system_path(path), expected=expected)
        
        # do a comparsion
        for name, opts in result.files.items():
            if 'expected' not in opts:
                continue

            if 'actual' not in opts:
                opts['error'] = 'file not found'
                msg = f"file <strong>{name}</strong> not found"
                if name == 'stdout':
                    msg = "Standard output (<strong>stdout</strong>) is empty"
                elif name == 'stderr':
                    msg = "Standard error (<strong>stderr</strong>) is empty. Did you mean to use this?<pre><code class='c'>fprintf(stderr, \"message\\n\");</code></pre>"

                result.add_result(False, msg)
                continue

            comparator = text_compare
            comparator_args = {'filters': filters}
            if name in self.tests.comparators:
                all_comparators = {
                    'binary': binary_compare,
                    'image': image_compare,
                }

                comparator = all_comparators[self.tests.comparators[name]['type']]
                comparator_args = {}

            success, output, diff = comparator(opts['expected'].path, opts['actual'].path, **comparator_args)
            if output:
                result.copy_html_result(name, output)
            if diff:
                result.copy_diff(name, diff)

            msg = f"file <strong>{name}</strong> doesn't match"
            if name == 'stdout':
                msg = "Standard output (<strong>stdout</strong>) doesn't match"
            elif name == 'stderr':
                msg = "Standard error (<strong>stderr</strong>) doesn't match"
            result.add_result(success, msg, output)

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

        if result['exitsig'] == "11":
            result.add_error("Segmentation fault")

        if test.exit_code is not None:
            result.add_result(test.exit_code == result['exit_code'], f"<strong>main</strong> or <strong>exit</strong> function terminated the program with exit status <strong>{result['exit_code']}</strong> instead of <strong>{test.exit_code}</strong>")

        # save issued commandline
        result['command'] = ' '.join(cmd)
        if test.stdin:
            result['command'] += f' < {shlex.quote(os.path.basename(test.stdin.path))}'

        # run custom evaluation script
        if test.script:
            check = getattr(test.script, 'check', None)
            if check:
                custom_result = check(result, self)
                if custom_result:
                    result.add_error(custom_result)

        return result

class Sandbox:
    def __init__(self):
        subprocess.check_call(["isolate", "--cleanup"])
        self.path = subprocess.check_output(["isolate", "--init", "--cg"]).decode('utf-8').strip()

    def system_path(self, path=''):
        return os.path.join(os.path.join(self.path, 'box'), path)

    def run(self, cmd, env=None, stderr_to_stdout=False):
        if not env:
            env = {}
        if 'PATH' not in env:
            env['PATH'] = '/usr/bin/:/bin'

        argv = [
            'isolate',
            '-s',
            '--run',
            '--processes=100',
            *env_build(env)
        ]

        if stderr_to_stdout:
            argv.append('--stderr-to-stdout')

        argv.append('--')
        argv += shlex.split(cmd)

        logger.info(f"executing in isolation: {shlex.join(argv)}")

        p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()

        res = {
            'exit_code': p.returncode,
            'stdout': stdout.decode('utf-8', errors='ignore'),
            'stderr': stderr.decode('utf-8', errors='ignore'),
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
        result['stderr'] = result['stderr'][:1024*10]
        result['command'] = command
        return result

# TODO: python3.8
def copytree(src, dst, symlinks=False, ignore=None):
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            shutil.copytree(s, d, symlinks, ignore)
        else:
            shutil.copy2(s, d)

def evaluate(task_path, submit_path, result_path, meta=None):
    '''
    Called by Django.
    '''

    sandbox = Sandbox()
    evaluation = Evaluation(task_path, result_path, sandbox, meta)

    logger.info(f"evaluating {submit_path}")
    # TODO: python3.8
    #shutil.copytree(submit_path, os.path.join(sandbox.path, "box/"), dirs_exist_ok=True)
    copytree(submit_path, os.path.join(sandbox.path, "box/"))


    return evaluation.run()
