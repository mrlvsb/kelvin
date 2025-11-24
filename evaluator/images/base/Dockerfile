FROM ubuntu:24.04

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    locales=2.39-0ubuntu8 \
    gcc=4:13.2.0-7ubuntu1 \
    g++=4:13.2.0-7ubuntu1 \
    gdb=15.0.50.20240403-0ubuntu1 \
    nasm=2.16.01-1build1 \
    python3=3.12.3-0ubuntu2.1 \
    cmake=3.28.3-1build7 && \
    rm -rf /var/lib/apt/lists/*

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3-pip && \
    rm -rf /var/lib/apt/lists/*

# For HTML sanitization
RUN python3 -m pip install --break-system-packages bleach==5.0.1

RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

# Workaround for https://github.com/dotnet/sdk/issues/31457
# It is included here, because it has to be present not only for building .NET projects,
# but also for running them (e.g. in the `run` image).
ENV DOTNET_EnableWriteXorExecute=0
