import json
import yaml
import os
import shlex
from collections import defaultdict
import subprocess
import tempfile

class DockerPipe:
    def __init__(self, image, **kwargs):
        self.image = image
        self.kwargs = kwargs

    def run(self, evaluation):
        result_dir = os.path.join(evaluation.result_path, self.id)
        os.mkdir(result_dir)

        env = ['-e' + shlex.quote(f"PIPE_{k.upper()}={v}") for k, v in self.kwargs.items()]
        args = [
            'docker', 'run', '--rm',
            '-w', '/work',
            '-v', evaluation.sandbox.system_path() + ':/work',
            *env,
            self.image
        ]

        def res_path(p):
            return os.path.join(result_dir, p)

        with open(res_path("stdout"), "w") as stdout, open(res_path("stderr"), "w") as stderr:
            p = subprocess.Popen(args, stdout=stdout, stderr=stderr)
            p.communicate()

        result = {}
        try:
            with open(os.path.join(evaluation.sandbox.system_path("piperesult.json"))) as f:
                result = json.load(f)
        except FileNotFoundError:
            pass

        if 'failed' not in result:
            result['failed'] = p.returncode != 0

        for f in ['stdout', 'stderr']:
            if os.path.getsize(res_path(f)) == 0:
                os.unlink(res_path(f))
        if not os.listdir(result_dir):
            os.unlink(result_dir)

        return result

class CommandPipe:
    def __init__(self, commands):
        self.commands = commands

    def run(self, evaluation):
        output = ""
        failed = False
        for command in self.commands:
            result = evaluation.sandbox.run(command, stderr_to_stdout=True)
            output += f"<code>$ {command}</code><br><pre>{result['stdout']}</pre>" 
            if result['exit_code'] != 0:
                failed = True
                break

        return {
            "html": output,
            "failed": failed,
        }

class RequiredFilesPipe:
    def __init__(self, files):
        self.files = files

    def run(self, evaluation):
        result = []
        for f in self.files:
            exists = os.path.exists(evaluation.sandbox.system_path(f))
            result.append(f"<li class='text-{'success' if exists else 'danger'}'>{f}</li>")


        return {
            "html": f"<ul>{''.join(result)}</ul>"
        }

class TestsPipe:
    def __init__(self, executable='./main'):
        self.executable = executable

    def run(self, evaluation):
        results = []
        for test in evaluation.tests:
            results.append(evaluation.evaluate(self.id, test, self.executable))

        return {
            "tests": results,
        }

class SleepPipe:
    def __init__(self, seconds=1):
        self.seconds = seconds

    def run(self, evaluation):
        import time
        time.sleep(self.seconds)
