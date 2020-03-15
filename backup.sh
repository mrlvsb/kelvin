#!/bin/bash
set -ex
dst="backups/$(date +"%Y-%m-%d_%H:%M:%S")"
mkdir -p "$dst"
cd "$dst"

rsync -avz kelvin@kelvin.cs.vsb.cz:kelvin/{db.sqlite3,submits} .
