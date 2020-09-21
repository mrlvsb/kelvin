#!/bin/bash
set -e
set -o pipefail

if [ -z "$PIPE_OUTPUT" ]; then
  PIPE_OUTPUT=main
fi

echo "<code>$ gcc $PIPE_FLAGS "*.c" -o $PIPE_OUTPUT</code>" > result.html
echo "<pre>" >> result.html
gcc $PIPE_FLAGS -o $PIPE_OUTPUT *.c |& sed 's/&/\&amp;/g; s/</\&lt;/g; s/>/\&gt;/g; s/"/\&quot;/g; s/'"'"'/\&#39;/g' | tee -a result.html
echo "</pre>" >> result.html
