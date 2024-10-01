FROM kelvin/run
RUN apt-get update &&  \
    apt-get install -y --no-install-recommends python3-pip python3-wheel && \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages pytest
