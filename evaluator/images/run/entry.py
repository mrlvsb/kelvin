#!/usr/bin/env python3
import os
import json
import subprocess
import shlex

with open("result.html", "w") as f:
    for job in json.loads(os.getenv('PIPE_COMMANDS')):
        if isinstance(job, str):
            job = {
                'cmd': job
            }
        if 'cmd' not in job:
            f.write("<span style='color:red'>Missing cmd key: {job}")
            continue

        if job['cmd'].startswith('#'):
            job['cmd'] = job['cmd'][1:]
            job['hide'] = True
        job['hide'] = job.get('hide', False)

        opts = {}
        if not job['hide']:
            f.write(f"<code>$ {job.get('cmd_show', job['cmd'])}</code><br>")
            f.write("<pre>")
            f.flush()
            opts['stdout'] = f
            opts['stderr'] = f
        p = subprocess.Popen(job['cmd'], shell=True, **opts)
        p.wait()
        if not job['hide']:
            f.write("</pre>")
            f.flush()

        if p.returncode:
            f.write(f'<span class="text-danger">Exited with return code {p.returncode}</span>')
            exit(1)

