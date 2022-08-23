FROM ubuntu:22.04

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    locales=2.35-0ubuntu3.1 \
    gcc=4:11.2.0-1ubuntu1 \
    g++=4:11.2.0-1ubuntu1 \
    gdb=12.0.90-0ubuntu1 \
    nasm=2.15.05-1 \
    python3=3.10.4-0ubuntu2 \
    cmake=3.22.1-1ubuntu1

RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8
