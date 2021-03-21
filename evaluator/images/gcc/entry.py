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
    env = {
        'CC': 'gcc',
        'CXX': 'g++',
        'CFLAGS': flags,
        'CXXFLAGS': flags,
        'LDFLAGS': ldflags,
        'CLICOLOR_FORCE': '1',
        'PATH': f'/wrapper:{os.getenv("PATH")}',
    }

    if 'cmakelists.txt' in [f.lower() for f in os.listdir('.')]:
        cmd_run(['cmake', '.'], out, env=env)

    if 'makefile' in [f.lower() for f in os.listdir('.')]:
        returncode = cmd_run(['make'], out, env=env)
    else:
        sources = []
        for root, dirs, files in os.walk('.'):
            for f in files:
                if f.split('.')[-1] in ['c', 'cpp']:
                    sources.append(os.path.join(root, f))

        if not sources:
            out.write("<span style='color: red'>Missing source files! please upload .c or .cpp files!</span>")
            exit(1)

        use_cpp = any(f.endswith('.cpp') for f in sources)
        compile_cmd = ["g++" if use_cpp else "gcc", *sources, "-o", output, *shlex.split(flags), *shlex.split(ldflags)]
        returncode = cmd_run(compile_cmd, out, show_cmd=compile_cmd, env=env)

    if output and not os.path.exists(output):
        executables = [f for f in os.listdir() if os.access(f, os.X_OK)]
        if len(executables) == 0:
            out.write("<span style='color: red'>No executable has been built.</span>")
            exit(1)
        elif len(executables) > 1:
            out.write("<span style='color: red'>Multiple executables have been built.</span>")
            exit(1)

        out.write(f"<code style='color: #444; font-weight: bold'>$ mv {executables[0]} {output}</code>")
        os.rename(executables[0], output)


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
