FROM ubuntu:18.04
RUN apt update && \
      apt install -y locales gcc g++ python3 cmake libsdl2-dev libsdl2-image-dev libsdl2-ttf-dev
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8