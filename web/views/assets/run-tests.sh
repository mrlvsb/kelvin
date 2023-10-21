#!/bin/bash

TABLE_OUTPUT=""
BINARY=${1:-./main}

if [ -f ${BINARY} ]
then
  RESULT=""
  for dir in */
  do
    ARGS=""
    if [ -f ${dir}args ]
    then
      ARGS=$(cat ${dir}args)
    fi
    ${BINARY} ${ARGS} < ${dir}stdin > ${dir}real_stdout 2> ${dir}real_stderr
    if ( [ ! -f ${dir}stdout ] || cmp --silent -- ${dir}stdout ${dir}real_stdout ) && ( [ ! -f ${dir}stderr ] || cmp --silent -- ${dir}stderr ${dir}real_stderr )
    then
      TABLE_OUTPUT="${TABLE_OUTPUT}${dir}:\t\u001b[32;1mSUCCESS\u001b[0m\n"
    else
      TABLE_OUTPUT="${TABLE_OUTPUT}${dir}:\t\u001b[31;1mFAILED\u001b[0m\n"
      if [ -f ${dir}stdout ]
      then
        git diff --no-index ${dir}real_stdout ${dir}stdout > ${dir}stdout.diff
      fi
      if [ -f ${dir}stderr ]
      then
        git diff --no-index ${dir}real_stderr ${dir}stderr > ${dir}stderr.diff
      fi
      RESULT="ERROR"
    fi
  done

  echo -e "${TABLE_OUTPUT}" | column -t

  if [ ${RESULT} ]
  then
    echo "You can find the program's outputs stored as \"real_stdout\" and output differences as \"stdout.diff\" in tests directories."
  fi
else
  echo -e "\u001b[31;1mERROR:\u001b[0m Binary not found."
fi
