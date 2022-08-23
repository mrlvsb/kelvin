FROM kelvin/run
RUN apt-get update &&  \
    apt-get install -y --no-install-recommends python3-pip && \
    rm -rf /var/lib/apt/lists/*

RUN pip3 install -U pip wheel setuptools
RUN pip3 install pytest
