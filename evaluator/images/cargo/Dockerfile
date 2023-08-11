FROM rust:1.71.0

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3-pip && \
    rm -rf /var/lib/apt/lists/*

# For HTML sanitization
RUN python3 -m pip install bleach==5.0.1

RUN rustup component add clippy

ADD entry.py /
CMD /entry.py
