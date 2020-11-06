#!/usr/bin/python3
import html
import subprocess
import os
import re
import shlex
import json
from collections import defaultdict

# TODO: replace with shlex.join on python3.8
def shlex_join(split_command):
    return ' '.join(shlex.quote(arg) for arg in split_command)

output = os.getenv('PIPE_OUTPUT', 'main')
flags = os.getenv('PIPE_FLAGS', '')

sources = []
for root, dirs, files in os.walk('.'):
    for f in files:
        if f.split('.')[-1] in ['c', 'cpp']:
            sources.append(os.path.join(root, f))

compile_cmd = ["gcc", *shlex.split(flags), "-o", output, *sources]

with open("result.html", "w") as out:
    if not sources:
        out.write("<span style='color: red'>Missing source files! please upload .c or .cpp files!</span>")
        exit(1)

    out.write(f"<code style='color: #444; font-weight: bold'>$ {shlex_join(compile_cmd)}</code>")

    with open('/tmp/out', 'w+', errors='ignore') as gcc_out:
        p = subprocess.Popen(compile_cmd, stdout=gcc_out, stderr=gcc_out)
        p.wait()

        gcc_out.seek(0)
        #out.write(f"<pre>{html.escape(gcc_out.read())}</pre>")

p = subprocess.Popen([*compile_cmd, '-fdiagnostics-format=json'], stderr=subprocess.PIPE)
stdout, stderr = p.communicate()
comments = defaultdict(list)
for err in json.loads(stderr.decode('utf-8')):
    for pos in err['locations']:
        filename = re.sub(r'^./', '', pos['caret']['file'])
        comments[filename].append({
            'line': pos['caret']['line'],
            'text': err['message'],
            'url': err.get('option_url', None),
 
        })

with open('piperesult.json', 'w') as out:
    json.dump({"comments": comments}, out, indent=4, sort_keys=True)

exit(p.returncode)
