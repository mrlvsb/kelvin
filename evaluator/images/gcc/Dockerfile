FROM ubuntu
RUN apt update && \
      apt install -y gcc-10 g++-10 python3 && \
      update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-10 1000 && \
      update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-10 1000
ADD entry.py /
CMD /entry.py
