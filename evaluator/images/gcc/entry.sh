#!/bin/sh
set -ex

if [ -z "$PIPE_OUTPUT" ]; then
  PIPE_OUTPUT=main
fi

gcc $PIPE_FLAGS -o $PIPE_OUTPUT *.c
