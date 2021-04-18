#!/bin/bash
set -ex

semester=2020-S

dst="backups/$(date +"%Y-%m-%d_%H:%M:%S")"
mkdir -p "$dst"
cd "$dst"

ssh kelvin@kelvin.cs.vsb.cz 'pg_dump kelvin | xz' | pv > dump.sql.xz
rsync -avzP kelvin@kelvin.cs.vsb.cz:kelvin/tasks .
mkdir submits
rsync -avzP "kelvin@kelvin.cs.vsb.cz:kelvin/submits/$semester" submits/
du -sh .
