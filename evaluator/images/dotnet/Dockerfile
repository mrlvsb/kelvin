FROM kelvin/base

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    dotnet7=7.0.108-0ubuntu1~23.04.1 \
    aspnetcore-runtime-7.0=7.0.108-0ubuntu1~23.04.1 \
    python3-pip && \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --break-system-packages bleach==5.0.1

ADD entry.py /
CMD /entry.py
