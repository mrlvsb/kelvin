#!/bin/bash
. .env
set -ex
ssh kelvin@kelvin.cs.vsb.cz docker exec kelvin_db pg_dump -U "$DATABASE__USERNAME" --clean kelvin | docker exec -i kelvin_db psql -U "$DATABASE__USERNAME" -d "$DATABASE__DB"
rsync -avzP --exclude='*/.dolos-results/' kelvin@kelvin.cs.vsb.cz:/srv/kelvin/kelvin/tasks .
rsync -avzP kelvin@kelvin.cs.vsb.cz:/srv/kelvin/kelvin/submits/2025-W submits/
rsync -avzP kelvin@kelvin.cs.vsb.cz:/srv/kelvin/kelvin/survey/surveys survey/
