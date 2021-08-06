FROM ubuntu:20.10
RUN apt update && \
      DEBIAN_FRONTEND=noninteractive apt install -y locales gcc g++ gdb nasm python3 cmake
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8
