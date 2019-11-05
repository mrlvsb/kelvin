#!/bin/sh
set -e
# configure api token
echo "{{ token }}" > ~/.upr-token

# install pip3 dependency on requests
if ! pip3 install --user requests; then
    echo "pip3 command not found"
    echo "try to install it"
    echo " $ apt install python3-pip"
    exit 1
fi

# download upr command
mkdir -p ~/.local/bin
wget -q {{request.scheme}}://{{request.META.HTTP_HOST}}{% url "upr.py" %} -O ~/.local/bin/upr
chmod +x ~/.local/bin/upr

# add ~/.local/bin to the PATH
line='export PATH=$PATH:~/.local/bin'
grep -qFx "$line" ~/.bashrc || echo "$line" >> ~/.bashrc

echo "upr command installed"
echo "open new terminal"