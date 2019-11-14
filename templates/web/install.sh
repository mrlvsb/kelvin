#!/bin/sh
set -e
# configure api token
echo "{{ token }}" > ~/.upr-token

if ! which python3 > /dev/null; then
    echo "Python3 missing, please try to install it:"
    echo "$ sudo apt install python3"
    exit 1
fi

# install pip3 as user if not present in the system
if ! which pip3 > /dev/null; then
    wget -q https://bootstrap.pypa.io/get-pip.py -O - | python3 - --user --no-warn-script-location
    export PATH=$PATH:$HOME/.local/bin
fi

# install pip3 dependency on requests
pip3 install --user --no-warn-script-location requests

# download upr command
mkdir -p ~/.local/bin
wget -q {{request.scheme}}://{{request.META.HTTP_HOST}}{% url "upr.py" %} -O ~/.local/bin/upr
chmod +x ~/.local/bin/upr

# add ~/.local/bin to the PATH
line='export PATH=$PATH:~/.local/bin'
grep -qFx "$line" ~/.bashrc || echo "$line" >> ~/.bashrc

echo "upr command installed"