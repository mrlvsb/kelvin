#!/bin/bash

set -eux

python manage.py migrate

# We need to run collection of static items after the container is started,
# because the static directory might be a Docker volume, and we need to overwrite it.
python manage.py collectstatic --no-input --clear

exec uwsgi --ini uwsgi.ini
