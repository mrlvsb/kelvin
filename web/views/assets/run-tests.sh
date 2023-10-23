#!/bin/bash

TABLE_OUTPUT=""
BINARY=${1:-./main}
BINARY=$(realpath "${BINARY}")

execute_test () {
  ${BINARY} $2 < $1/stdin > $1/real_stdout 2> $1/real_stderr
  local CODE=$?
  local CODEMESSAGE=""
  if [ ${CODE} != $3 ]
  then
    local CODEMESSAGE=" (return code \u001b[1m$3\u001b[0m expected, \u001b[1m${CODE}\u001b[0m given)"
  fi
  if ( [ ! -f $1/stdout ] || cmp --silent -- $1/stdout $1/real_stdout ) && ( [ ! -f $1/stderr ] || cmp --silent -- $1/stderr $1/real_stderr ) && [ ! "${CODEMESSAGE}" ]
  then
    TABLE_OUTPUT="${TABLE_OUTPUT}$1:\t\u001b[32;1mSUCCESS\u001b[0m\n"
  else
    TABLE_OUTPUT="${TABLE_OUTPUT}$1:\t\u001b[31;1mFAILED\u001b[0m${CODEMESSAGE}\n"
    if [ -f $1/stdout ]
    then
      git diff --no-index $1/real_stdout $1/stdout > $1/stdout.diff
    fi
    if [ -f $1/stderr ]
    then
      git diff --no-index $1/real_stderr $1/stderr > $1/stderr.diff
    fi
    RESULT="ERROR"
  fi
}

if [ -f ${BINARY} ]
then
  RESULT=""

  # --kelvin-generate--
  echo -e "${TABLE_OUTPUT}" | column -ts $'\t'

  if [ ${RESULT} ]
  then
    echo "You can find the program's outputs stored as \"real_stdout\" and output differences as \"stdout.diff\" in tests directories."
  fi
else
  echo -e "\u001b[31;1mERROR:\u001b[0m Binary not found."
fi
