FROM ubuntu:18.04
RUN apt update && \
      apt install -y gcc g++ python3 cmake libsdl2-dev libsdl2-image-dev libsdl2-ttf-dev 
ADD entry.py /
CMD /entry.py
