#!/bin/bash
ssh kelvin@kelvin.cs.vsb.cz << COMMANDS
  set -ex
  cd kelvin
  git pull
  pip install -r requirements.txt
  python manage.py migrate
  (
    cd frontend
    npm install
    npm run build
  )
  python manage.py collectstatic --no-input -c
  sudo systemctl restart uwsgi "kelvin-worker@*"
  cd evaluator/images && ./build.sh
  curl https://sentry.io/api/hooks/release/builtin/5459340/e234046479d3446064962c594a05b10e3acdb0ae6dd9985383e42773a7d79c0c/ \
    -X POST \
    -H 'Content-Type: application/json' \
    -d '{"version": "'$(git rev-parse HEAD)'"}'
  echo OK
COMMANDS


