#!/usr/bin/env python3
from fabric import task, Connection

c = Connection("kelvin@upr.cs.vsb.cz")
with c.cd("kelvin"):
    c.run("git pull")
    c.run("~/venv/bin/pip install -r requirements.txt")
    c.run("~/venv/bin/python manage.py migrate")
    c.run("~/venv/bin/python manage.py collectstatic --no-input -c")

c.sudo("systemctl restart uwsgi kelvin-worker@0")

