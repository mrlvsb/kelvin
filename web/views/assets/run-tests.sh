#!/bin/bash

# Usage: ./run-tests.sh <path-to-binary>
# Example: ./run-tests.sh ./main

TABLE_OUTPUT=""
BINARY=${1:-./main}
SCRIPT_PATH=$(dirname $(realpath $0))
command -v git &> /dev/null
HAS_GIT=$?

execute_test () {
  local TEST_PATH="${SCRIPT_PATH}/$1"
  ${BINARY} $2 < ${TEST_PATH}/stdin > ${TEST_PATH}/real_stdout 2> ${TEST_PATH}/real_stderr
  local CODE=$?
  local CODEMESSAGE=""
  if [ ${CODE} != $3 ]
  then
    local CODEMESSAGE=" (return code `tput bold`$3`tput sgr0` expected, `tput bold`${CODE}`tput setgr0` given)"
  fi
  if ( [ ! -f ${TEST_PATH}/stdout ] || cmp --silent -- ${TEST_PATH}/stdout ${TEST_PATH}/real_stdout ) && ( [ ! -f ${TEST_PATH}/stderr ] || cmp --silent -- ${TEST_PATH}/stderr ${TEST_PATH}/real_stderr ) && [ ! "${CODEMESSAGE}" ]
  then
    TABLE_OUTPUT="${TABLE_OUTPUT}$1:\t`tput bold setaf 2`SUCCESS`tput sgr0`\n"
  else
    TABLE_OUTPUT="${TABLE_OUTPUT}$1:\t`tput bold setaf 1`FAILED`tput sgr0`${CODEMESSAGE}\n"
    if [ ${HAS_GIT} -eq 0 ]
    then
      if [ -f ${TEST_PATH}/stdout ]
      then
        git diff --no-index ${TEST_PATH}/real_stdout ${TEST_PATH}/stdout > ${TEST_PATH}/stdout.diff
      fi
      if [ -f ${TEST_PATH}/stderr ]
      then
        git diff --no-index ${TEST_PATH}/real_stderr ${TEST_PATH}/stderr > ${TEST_PATH}/stderr.diff
      fi
    fi
    RESULT="ERROR"
  fi
}

if [ -f ${BINARY} ]
then
  BINARY=$(realpath "${BINARY}")
  RESULT=""

  # --kelvin-generate--
  echo -e "${TABLE_OUTPUT}" | column -ts $'\t'

  if [ ${RESULT} ]
  then
    if [ ${HAS_GIT} -eq 0 ]
    then
      echo "You can find the program's outputs stored as \"real_stdout\" and output differences as \"stdout.diff\" in tests directories."
    else
      echo "You can find the program's outputs stored as \"real_stdout\" in tests directories."
      echo "If you want to include output differences, please install Git."
    fi
  fi
else
  echo -e "`tput bold setaf 1`ERROR:`tput sgr0` Binary not found."
fi
