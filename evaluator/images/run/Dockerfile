FROM kelvin/base

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y asciinema imagemagick webp python3-magic \
    openjdk-21-jdk && \
    rm -rf /var/lib/apt/lists/*

ADD entry.py /
CMD /entry.py
