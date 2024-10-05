#!/bin/bash

python manage.py migrate

exec uwsgi --ini uwsgi.ini
