FROM ubuntu:23.04

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    locales=2.37-0ubuntu2 \
    gcc=4:12.2.0-3ubuntu1 \
    g++=4:12.2.0-3ubuntu1 \
    gdb=13.1-2ubuntu2 \
    nasm=2.16.01-1 \
    python3=3.11.2-1 \
    cmake=3.25.1-1ubuntu1 && \
    rm -rf /var/lib/apt/lists/*

RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8
