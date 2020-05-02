import json
import yaml
import os
import shlex
from collections import defaultdict
import subprocess
import tempfile


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

class GcclinterPipe:
    def __init__(self, compiler, flags=None):
        self.compiler = compiler

        if not flags:
            flags = ['-Wall']

        self.flags = flags

    def run(self, evaluation):
        sources = [f for f in os.listdir(evaluation.sandbox.system_path()) if f.endswith(".c") or f.endswith(".cpp")]
        cmd = [
            self.compiler,
            '-fdiagnostics-format=json',
            *self.flags,
            *sources
        ]
        result = evaluation.sandbox.run(shlex.join(cmd), stderr_to_stdout=True)

        comments = defaultdict(list)
        for line in result['stdout'].split('\n'):
            if not line.strip():
                continue
            for err in json.loads(line):
                for pos in err['locations']:
                    comments[pos['caret']['file']].append({
                        'line': pos['caret']['line'],
                        'text': err['message'],
                    })

        return {
            "comments": comments,
        }

class ClangtidyPipe:
    class OffsetToLine:
        def __init__(self, root):
            self.root = root
            self.files = {}

        def to_line(self, path, offset):
            if path not in self.files:
                self.files[path] = self.build(path)

            for line, threshold in enumerate(self.files[path]):
                if threshold > offset:
                    return line + 1

        def build(self, path):
            offsets = []
            with open(os.path.join(self.root, path), "rb") as f:
                for offset, byte in enumerate(f.read()):
                    if byte == ord('\n'):
                        offsets.append(offset)
            return offsets

    def __init__(self, checks=None):
        self.checks = [] if not checks else checks

    def run(self, evaluation):
        with tempfile.NamedTemporaryFile() as f:
            sources = [os.path.basename(f) for f in os.listdir(evaluation.sandbox.system_path()) if f.endswith(".c") or f.endswith(".cpp")]
            print(["clang-tidy", "--export-fixes=" + f.name, *sources])

            subprocess.Popen(["clang-tidy", f"-checks={','.join(self.checks)}", f"--export-fixes={f.name}", *sources], cwd=evaluation.sandbox.system_path()).wait()

            offset_to_line = ClangtidyPipe.OffsetToLine(evaluation.sandbox.system_path())
            comments = defaultdict(list)
            f.seek(0)
            for err in yaml.load(f.read(), Loader=yaml.SafeLoader)['Diagnostics']:
                seen = set()

                for note in [err, err['DiagnosticMessage'] if 'DiagnosticMessage' in err else {}]: #, *err['Notes']]:
                    if 'Message' not in note or note['Message'] in seen:
                        continue
                    seen.add(note['Message'])
                    source = os.path.basename(note['FilePath'])
                    comments[source].append({
                        'line': offset_to_line.to_line(source, note['FileOffset']),
                        'text': note['Message'],
                        'source': err['DiagnosticName'],
                    })


            return {
                "comments": comments,
            }

