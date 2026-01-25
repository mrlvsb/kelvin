FROM kelvin/gcc

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y \
    -o APT::Install-Recommends=false \
    -o APT::Install-Suggests=false \
    clang-tidy python3-yaml \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ADD analyze.py build_urls.py /
RUN /build_urls.py
CMD /analyze.py
