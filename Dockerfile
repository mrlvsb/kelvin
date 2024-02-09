FROM python:3.12

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y libsasl2-dev libgraphviz-dev graphviz pandoc

COPY requirements.txt /kelvin/requirements.txt
RUN pip install --upgrade pip
RUN pip install -r /kelvin/requirements.txt

RUN apt-get update \
      && apt-get install -y ca-certificates curl gnupg lsb-release \
      && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
      && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list \
      && apt-get update \
      && apt-get install -y docker-ce docker-ce-cli containerd.io

WORKDIR /kelvin

#RUN addgroup --gid 1000 user
#RUN adduser --disabled-password --gecos '' --uid $HOST_USER_ID --gid 1000 user
#USER user
