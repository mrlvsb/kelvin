#!/usr/bin/env python3
import os
import subprocess
from collections import defaultdict
import json
import shlex


cmd = [
    'gcc',
    '-fdiagnostics-format=json',
    *shlex.split(os.environ.get('PIPE_FLAGS', '-Wall'))
]

cmd += [os.path.basename(f) for f in os.listdir() if f.endswith(".c") or f.endswith(".cpp")]
print(cmd)
out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)

comments = defaultdict(list)
for err in json.loads(out):
    for pos in err['locations']:
        comments[pos['caret']['file']].append({
            'line': pos['caret']['line'],
            'text': err['message'],
        })
 
with open('piperesult.json', 'w') as out:
    json.dump({"comments": comments}, out, indent=4, sort_keys=True)

