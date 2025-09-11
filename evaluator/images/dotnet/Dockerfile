FROM kelvin/base

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    software-properties-common

RUN add-apt-repository ppa:dotnet/backports

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    dotnet-sdk-9.0 \
    aspnetcore-runtime-9.0 \
    python3-pip && \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --break-system-packages bleach==5.0.1

ADD entry.py /
CMD /entry.py
