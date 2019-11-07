#!/bin/sh
inotifywait -e create -rm submits/ --format %w%f | while read -r line; do
  echo $line
  sleep 1
  ./manage.py evaluate "$line"
done 
