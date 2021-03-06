#!/bin/bash
set -e
for d in */; do (
  echo "$d"
  cd "$d" || exit
  docker build -t "kelvin/${d::-1}" .
) done

