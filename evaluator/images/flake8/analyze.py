#!/usr/bin/env python3
import os
import subprocess
from collections import defaultdict
import json


def addlist(name):
    items = os.getenv(f'PIPE_{name.upper()}')
    if items:
        try:
            items = json.loads(items)
            if isinstance(items, list):
                items = ",".join(items)
        except json.decoder.JSONDecodeError:
            pass
        return [f"--{name}", items]
    return []

cmd = [
    "flake8",
    "--format=%(path)s:%(row)d:%(code)s:%(text)s",
    *addlist('select'),
    *addlist('ignore'),
]

print(cmd)

# (file, line) -> [text]
lint_results = defaultdict(list)

p = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
for line in p.stdout.readlines():
    path, line, code, text = line.strip().split(':', 3)

    file_path = os.path.normpath(path)
    line = int(line)
    lint_results[(file_path, line)].append(f'{text} [{code}]')

comments = defaultdict(list)
for ((file, line), texts) in lint_results.items():
    comments[file].append({
        "line": line,
        "text": ", ".join(texts),
        "source": "flake8"
    })

with open('piperesult.json', 'w') as out:
    json.dump({"comments": comments}, out, indent=4, sort_keys=True)
