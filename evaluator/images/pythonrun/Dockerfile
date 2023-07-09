FROM kelvin/run
RUN apt-get update &&  \
    apt-get install -y --no-install-recommends python3-pip && \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install --break-system-packages -U pip wheel setuptools
RUN pip3 install --break-system-packages pytest
