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

        with open(os.path.join(result_dir, "stdout"), "w") as stdout, open(os.path.join(result_dir, "stderr"), "w") as stderr:
            p = subprocess.Popen(args, stdout=stdout, stderr=stderr)
            p.communicate()

        try:
            with open(evaluation.sandbox.system_path("piperesult.json")) as f:
                return json.load(f)
        except FileNotFoundError:
            pass

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
