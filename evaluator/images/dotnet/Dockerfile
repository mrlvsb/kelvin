FROM kelvin/base

ENV DOTNET_EnableWriteXorExecute=0

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y \
    -o APT::Install-Recommends=false \
    -o APT::Install-Suggests=false \
    software-properties-common

RUN add-apt-repository ppa:dotnet/backports

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y \
    -o APT::Install-Recommends=false \
    -o APT::Install-Suggests=false \
    dotnet-sdk-9.0 \
    aspnetcore-runtime-9.0 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ADD entry.py /
CMD /entry.py
