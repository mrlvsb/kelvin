#!/bin/bash
set -e
set -o pipefail
shopt -s nullglob

if [ -z "$PIPE_OUTPUT" ]; then
  PIPE_OUTPUT=main
fi

if [ -z *.{cpp,c} ]; then
  echo "<span style='color: red'>Missing source files! please upload .c or .cpp files!</span>" > result.html
  exit 1
fi

echo "<code>$ gcc $PIPE_FLAGS " *.{cpp,c} " -o $PIPE_OUTPUT</code>" > result.html
echo "<pre>" >> result.html
gcc $PIPE_FLAGS -o $PIPE_OUTPUT *.{cpp,c} |& sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g; s/"/\&quot;/g; s/'"'"'/\&#39;/g' | tee -a result.html
echo "</pre>" >> result.html
