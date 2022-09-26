FROM kelvin/base

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    dotnet6 \
    aspnetcore-runtime-6.0 \
    python3-pip && \
    rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install bleach==5.0.1

ADD entry.py /
CMD /entry.py
