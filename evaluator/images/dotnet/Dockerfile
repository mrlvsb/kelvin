FROM kelvin/base

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
    dotnet6=6.0.108-0ubuntu1~22.04.1 \
    aspnetcore-runtime-6.0=6.0.108-0ubuntu1~22.04.1 \
    python3-pip

RUN python3 -m pip install bleach==5.0.1

ADD entry.py /
CMD /entry.py
