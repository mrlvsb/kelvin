FROM ubuntu:21.04

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    locales=2.33-0ubuntu5 \
    gcc=4:10.3.0-1ubuntu1 \
    g++=4:10.3.0-1ubuntu1 \
    gdb=10.1-2ubuntu2 \
    nasm=2.15.05-1 \
    python3=3.9.4-1 \
    cmake=3.18.4-2ubuntu1

RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8
