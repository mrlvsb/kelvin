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

def cmd_run(cmd, out, show_cmd=None, env=None):
    if not show_cmd:
        show_cmd = cmd

    if env:
        env = {**os.environ, **env}

    out.write(f"<code style='color: #444; font-weight: bold'>$ {shlex_join(show_cmd)}</code>")

    with open('/tmp/out', 'w+', errors='ignore') as gcc_out:
        p = subprocess.Popen(cmd, stdout=gcc_out, stderr=gcc_out, env=env)
        p.wait()

        gcc_out.seek(0)
        out.write(f"<kelvin-terminal-output>{html.escape(gcc_out.read())}</kelvin-terminal-output>")
        return p.returncode

output = os.getenv('PIPE_OUTPUT', 'main')
flags = os.getenv('PIPE_FLAGS', '')
ldflags = os.getenv('PIPE_LDFLAGS', '')

with open("result.html", "w") as out:
    if os.path.exists('Makefile'):
        returncode = cmd_run(['make'], out, env={
            'CC': 'gcc',
            'CXX': 'g++',
            'CFLAGS': flags,
            'LDFLAGS': ldflags,
        })
    else:
        sources = []
        for root, dirs, files in os.walk('.'):
            for f in files:
                if f.split('.')[-1] in ['c', 'cpp']:
                    sources.append(os.path.join(root, f))

        if not sources:
            out.write("<span style='color: red'>Missing source files! please upload .c or .cpp files!</span>")
            exit(1)

        compile_cmd = ["gcc", *sources, "-o", output, *shlex.split(flags), *shlex.split(flags)]
        returncode = cmd_run(compile_cmd + ['-fdiagnostics-color=always'], out, show_cmd=compile_cmd)

"""
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
"""
exit(returncode)
