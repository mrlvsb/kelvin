#!/bin/sh
set -ex
echo "{{ token }}" > ~/.upr-token
pip install --user requests
mkdir -p ~/.local/bin
wget {{request.scheme}}://{{request.META.HTTP_HOST}}{% url "upr.py" %} -O ~/.local/bin/upr