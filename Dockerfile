FROM python:3

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y libldap2-dev libsasl2-dev graphviz-dev pandoc

COPY requirements.txt /kelvin/requirements.txt
RUN pip install -r /kelvin/requirements.txt

WORKDIR /kelvin

#RUN addgroup --gid 1000 user
#RUN adduser --disabled-password --gecos '' --uid $HOST_USER_ID --gid 1000 user
#USER user
