FROM python:3.13-slim-trixie AS build
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=python3.13 \
    UV_PROJECT_ENVIRONMENT=/app

RUN --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync \
        --locked \
        --no-dev \
        --no-install-project

COPY . /src

WORKDIR /src

RUN uv sync \
        --locked \
        --no-dev \
        --no-editable

FROM python:3.13-slim-trixie AS runtime

RUN groupadd -g 1000 webserver && useradd --uid 1000 --gid 1000 --shell /bin/false --system webserver

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y \
    -o APT::Install-Recommends=false \
    -o APT::Install-Suggests=false \
    git \
    ca-certificates \
    curl

RUN curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
RUN chmod a+r /etc/apt/keyrings/docker.asc

RUN echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
    tee /etc/apt/sources.list.d/docker.list > /dev/null

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y \
    -o APT::Install-Recommends=false \
    -o APT::Install-Suggests=false \
    docker-ce docker-ce-cli containerd.io docker-compose-plugin && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ENV PATH="/app/bin:$PATH"

COPY --from=build --chown=webserver:webserver /app /app

COPY --chown=webserver:webserver healthcheck.py /app/healthcheck.py

WORKDIR /app

USER webserver

ENV HOME=/tmp

RUN git config --global --add safe.directory "*"

# Test if the application can be imported
RUN <<EOT
python -Im site
python -Ic 'import app'
EOT

ENTRYPOINT [ "uvicorn" , "app.main:app", "--workers", "1", "--loop", "uvloop", "--host", "0.0.0.0" ]

CMD ["--port", "9000", "--root-path", "/deployment"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["python3", "/app/healthcheck.py"]
