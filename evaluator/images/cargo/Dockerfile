FROM rust:1.90.0

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y \
    -o APT::Install-Recommends=false \
    -o APT::Install-Suggests=false \
    python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# For HTML sanitization
RUN python3 -m pip install --break-system-packages bleach==6.3.0

RUN rustup component add clippy
