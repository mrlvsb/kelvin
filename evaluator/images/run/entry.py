#!/usr/bin/env python3
import os
import json
import subprocess
import html
from io import StringIO

with open("result.html", "w") as f:
    for job in json.loads(os.getenv('PIPE_COMMANDS')):
        if isinstance(job, str):
            job = {
                'cmd': job
            }
        if 'cmd' not in job:
            f.write("<span style='color:red'>Missing cmd key: {html.escape(job)}")
            continue

        if job['cmd'].startswith('#'):
            job['cmd'] = job['cmd'][1:]
            job['hide'] = True

        with open('/tmp/out', 'w+', errors='ignore') as out:
            p = subprocess.Popen(job['cmd'], shell=True, stdout=out, stderr=out)
            p.wait()

            if not job.get('hide', False):
                out.seek(0)
                f.write(f"<code style='color: #444; font-weight: bold'>$ {html.escape(job.get('cmd_show', job['cmd']))}</code><br>")
                f.write(f"<pre>{html.escape(out.read())}</pre>")

        if p.returncode:
            f.write(f'<span class="text-danger">Exited with return code {p.returncode}</span>')
            exit(1)

