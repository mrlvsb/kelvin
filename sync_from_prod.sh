#!/bin/bash
. .env
ssh kelvin@kelvin.cs.vsb.cz pg_dump --clean kelvin | docker exec -i kelvin_db psql -U "$DB_USERNAME" -d "$DB_DATABASE"
rsync -avzP kelvin@kelvin.cs.vsb.cz:kelvin/tasks . 
rsync -avzP kelvin@kelvin.cs.vsb.cz:kelvin/submits/2021-S submits/ 
rsync -avzP kelvin@kelvin.cs.vsb.cz:kelvin/survey/surveys survey/
