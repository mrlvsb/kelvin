#!/bin/bash
docker rm -f kelvin_pgsql
docker run -p 127.0.0.1:5432:5432 --name kelvin_pgsql -e POSTGRES_PASSWORD=pazzword -d postgres
sleep 5
ssh kelvin@kelvin.cs.vsb.cz pg_dump kelvin | pv | docker exec -i kelvin_pgsql psql -U postgres -d postgres
rsync -avzP kelvin@kelvin.cs.vsb.cz:kelvin/{tasks,exams} . 
rsync -avzP kelvin@kelvin.cs.vsb.cz:kelvin/submits/2021-W submits/ 
rsync -avzP kelvin@kelvin.cs.vsb.cz:kelvin/survey/surveys survey/
