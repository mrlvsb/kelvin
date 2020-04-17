import json
import yaml
import os
from collections import defaultdict


class CommandPipe:
    def __init__(self, commands):
        self.commands = commands

    def run(self, evaluation):
        output = ""
        for command in self.commands:
            result = evaluation.sandbox.run(command, stderr_to_stdout=True)
            output += f"<code>$ {command}</code><br><pre>{result['stdout']}</pre>" 

        return {
            "html": output,
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
    def run(self, evaluation):
        result = evaluation.sandbox.run('g++ rds_reader.cpp -Wall -fdiagnostics-format=json', stderr_to_stdout=True)

        comments = defaultdict(list)
        for err in json.loads(result['stdout']):
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
            import logging
            logging.error(path)
            with open(os.path.join(self.root, path), "rb") as f:
                for offset, byte in enumerate(f.read()):
                    if byte == ord('\n'):
                        offsets.append(offset)
            return offsets


    def run(self, evaluation):
        result = evaluation.sandbox.run('sh -c "clang-tidy *.cpp --export-fixes=errors 2>/dev/null >/dev/null; cat errors"')

        offset_to_line = ClangtidyPipe.OffsetToLine(evaluation.sandbox.system_path())
        comments = defaultdict(list)
        for err in yaml.load(result['stdout'], Loader=yaml.SafeLoader)['Diagnostics']:
            seen = set()

            for note in [err, err['DiagnosticMessage'] if 'DiagnosticMessage' in err else {}]: #, *err['Notes']]:
                if 'Message' not in note or note['Message'] in seen:
                    continue
                seen.add(note['Message'])
                source = note['FilePath'][5:]
                comments[source].append({
                    'line': offset_to_line.to_line(source, note['FileOffset']),
                    'text': note['Message'],
                })


        return {
            "comments": comments,
        }

