#!/usr/bin/env python3
import os
import json
import subprocess
import html
import base64
from io import StringIO
import glob
import magic

mimes = mime = magic.Magic(mime=True)

SUPPORTED_IMAGES = [
    'image/png',
    'image/jpeg',
    'image/gif',
    'image/webp',
    'image/svg+xml',
]

DEFAULT_TIMEOUT=5

def display(patterns, out, delete=False):
    for pattern in patterns:
        for filename in glob.glob(pattern):
            out.write(f"<strong>{html.escape(filename)}</strong><br>")
            try:
                mimetype = mimes.from_file(filename)
                if mimetype.startswith('image/'):
                    toshow = filename
                    if mimetype not in SUPPORTED_IMAGES:
                        toshow = "/tmp/image.webp"
                        subprocess.check_call(["convert", filename, toshow])
                    
                    with open(toshow, 'rb') as f:
                        out.write(f"<img src='data:image/webp;base64,{base64.b64encode(f.read()).decode('utf-8')}' />")

                    if delete:
                        try:
                            os.unlink(filename)
                        except Exception as e:
                            out.write(f"Could not delete: {e}")
                else:
                    out.write(f"<p class='text-danger'>Unsupported file {filename}</p>")
            except Exception as e:
                out.write(f"<p class='text-danger'>Failed to show file {filename}: {e}</p>")
            
            out.write("<br>")

with open("result.html", "w") as f:
    for job in json.loads(os.getenv('PIPE_COMMANDS')):
        if isinstance(job, str):
            job = {
                'cmd': job
            }
        if 'display' in job:
            display(job['display'], f, delete=job.get('delete', False))
            continue
        elif 'cmd' not in job:
            f.write(f"<span style='color:red'>Missing cmd key: {html.escape(job)}")
            continue

        if job['cmd'].startswith('#'):
            job['cmd'] = job['cmd'][1:]
            job['hide'] = True

        if not job.get('hide', False):
            f.write(f"<code style='color: #444; font-weight: bold'>$ {html.escape(job.get('cmd_show', job['cmd']))}</code><br>")
        if job.get('asciinema', False):
            cmd = ['asciinema', 'rec', '-c', f"timeout {job.get('timeout', DEFAULT_TIMEOUT)} {job['cmd']}", '/tmp/out.cast']
            p = subprocess.Popen(cmd, env={**os.environ, 'TERM': 'xterm', 'HOME': '/tmp'})
            p.wait()

            with open("/tmp/out.cast", "rb") as record:
                f.write(f"<asciinema-player preload src='data:application/json;base64,{base64.b64encode(record.read()).decode('utf-8')}'></asciinema-player>")
        else:
            with open('/tmp/out', 'w+', errors='ignore') as out:
                timedout = False
                try:
                    p = subprocess.Popen(job['cmd'], shell=True, bufsize=1, stdout=out, stderr=out)
                    p.wait(timeout=job.get('timeout', DEFAULT_TIMEOUT))
                except subprocess.TimeoutExpired:
                    p.kill()
                    timedout = True

                if not job.get('hide', False):
                    out.seek(0)
                    f.write(f"<kelvin-terminal-output>{html.escape(out.read())}</kelvin-terminal-output>")

                if timedout:
                    f.write(f'<span class="text-danger">Process timed out after {job.get("timeout", DEFAULT_TIMEOUT)} seconds</span>')
                    exit(1)

        if p.returncode:
            f.write(f'<span class="text-danger">Exited with return code {p.returncode}</span>')
            exit(1)

