#!/bin/bash

set -eux

python manage.py migrate

exec uwsgi --ini uwsgi.ini
