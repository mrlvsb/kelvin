#!/bin/bash
. .env
set -ex
ssh kelvin@kelvin.cs.vsb.cz pg_dump --clean kelvin | docker exec -i kelvin_db psql -U "$DATABASE__USERNAME" -d "$DATABASE__DB"
rsync -avzP kelvin@kelvin.cs.vsb.cz:kelvin/tasks . 
rsync -avzP kelvin@kelvin.cs.vsb.cz:kelvin/submits/2023-W submits/
rsync -avzP kelvin@kelvin.cs.vsb.cz:kelvin/survey/surveys survey/
