#!/usr/bin/env python3
from fabric import task, Connection

c = Connection("kelvin@upr.cs.vsb.cz")
with c.cd("kelvin"):
    c.run("git stash")
    c.run("git pull")
    c.run("git stash pop")
    c.run("~/venv/bin/python manage.py migrate")
    c.run("~/venv/bin/python manage.py collectstatic --no-input")

c.sudo("systemctl restart uwsgi kelvin-worker@0")

