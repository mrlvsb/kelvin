from django.core.management.base import BaseCommand, CommandError
import subprocess
from shutil import copyfile
import os
import glob
import shlex
import re
import tarfile

from kelvin.models import Submit
import json


class Sandbox:
    def __init__(self):
        subprocess.check_call(["isolate", "--cleanup"])
        self.path = subprocess.check_output(["isolate", "--init", "--cg"]).decode('utf-8').strip()

    def system_path(self, path):
        return os.path.join(os.path.join(self.path, 'box'), path)

    def run(self, cmd):
        p = subprocess.Popen(shlex.split("isolate -s --run --processes=100 -e -- " + cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.wait() # TODO: may not work!

        return {
            'exit_code': p.returncode,
            'stdout': p.stdout.read().decode('utf-8'),
            'stderr': p.stderr.read().decode('utf-8'),
        }

    def run_check(self, cmd):
        ret = self.run(cmd)
        if ret['exit_code'] != 0:
            raise "failed to execute:" + cmd
        return ret

class GccPipeline:
    def __init__(self, tpl, gcc_params=""):
        self.gcc_params = gcc_params
        self.tpl = tpl

    def run(self, sandbox):
        gcc_result = sandbox.run_check("/usr/bin/gcc main.c -o main -g " + self.gcc_params)

        tests = []
        tpl = self.tpl
        for out in glob.glob(os.path.join(tpl, '*.out')):
            print(out);
            test_name = os.path.basename(re.sub('.out$', '', out))

            args = {}

            test_stdin = os.path.join(tpl, f"{test_name}.in")
            print(test_stdin)
            if os.path.exists(test_stdin):
                print("openin")
                args['stdin'] = open(test_stdin, "r")
            
            p = subprocess.Popen(shlex.split("isolate -M /tmp/meta --processes=5 -s --run -- ./main"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, **args)
            p.wait()

            stdout = p.stdout.read().decode('utf-8')
            expected = open(out).read()

            meta = {}
            with open('/tmp/meta') as f:
                for line in f:
                    key, val = line.split(':')
                    key = key.strip().replace('-', '')
                    val = val.strip()

                    if key != 'exitcode':
                        meta[key] = val

            tests.append({**{
                'name': test_name,
                'stdout': stdout,
                'stderr': p.stderr.read().decode('utf-8'),
                'expected': expected,
                'exit_code': p.returncode,
                'success': stdout == expected
            }, **meta})

        return {
            "gcc": gcc_result,
            "tests": tests,
        }

class DownloadPipe:
    def run(self, sandbox: Sandbox):
        src = 'submit'
        if tarfile.is_tarfile(sandbox.system_path(src)):
            sandbox.run_check('tar -xf {}'.format(src))
        else:
            sandbox.run_check('/bin/mv {} main.c'.format(src))


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('submit_file')

    def handle(self, *args, **opts):
        submit = Submit.objects.get(source=opts['submit_file'])

        tpl = "tasks/{}".format(submit.task.code)

        result = []

        sandbox = Sandbox()
        copyfile(submit.source.path, os.path.join(sandbox.path, "box/submit"))

        pipeline = [
            ('download', DownloadPipe()),
            ('normal run', GccPipeline(tpl)),
            ('run with sanitizer', GccPipeline(tpl, '-fsanitize=address -fsanitize=bounds -fsanitize=undefined')),
        ]
        
        for name, pipe in pipeline:
            res = pipe.run(sandbox)
            if res:
                result.append({'name': name, **res})
        

        #from pprint import pprint
        #pprint(result)

        submit.points = 0
        submit.max_points = 0
        for i in result:
            for test in i['tests']:
                if test['success']:
                    submit.points += 1
                submit.max_points += 1


        submit.result = json.dumps(result, indent=4)
        submit.save()