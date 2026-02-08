FROM python:3.12-slim-bookworm AS build-backend

COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /usr/local/bin/uv

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y \
    -o APT::Install-Recommends=false \
    -o APT::Install-Suggests=false \
    build-essential \
    libsasl2-dev \
    libgraphviz-dev

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project --compile-bytecode

FROM node:22.9.0-bookworm-slim AS build-frontend

WORKDIR /frontend

COPY frontend .

RUN mkdir -p /web/static

RUN npm ci

RUN npm run build

FROM python:3.12-slim-bookworm AS runtime

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y \
    -o APT::Install-Recommends=false \
    -o APT::Install-Suggests=false \
    graphviz \
    libmagic1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /app

# Create new user to run app process as unprivileged user
# We want to use ID 1000, to have the same ID as the default outside user
# And we also want group 101, to provide share access to the Unix uWSGI
# socket with the nginx image.
RUN getent group 101 >/dev/null || groupadd -g 101 webserver

RUN useradd --uid 1000 --gid 101 --shell /bin/false --system webserver

RUN chown -R webserver .

COPY --from=build-backend --chown=webserver /app .
ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=webserver web ./web
COPY --chown=webserver kelvin ./kelvin
COPY --chown=webserver templates ./templates
COPY --chown=webserver evaluator ./evaluator
COPY --chown=webserver survey ./survey
COPY --chown=webserver common ./common
COPY --chown=webserver api ./api
COPY --chown=webserver quiz ./quiz
COPY --chown=webserver manage.py .
COPY --from=build-frontend --chown=webserver /web/static/ ./web/static/

RUN mkdir -p /socket && chown webserver /socket

USER webserver

RUN python manage.py collectstatic --no-input --clear

COPY --chown=webserver deploy/entrypoint.sh ./

STOPSIGNAL SIGINT

ENTRYPOINT ["/app/entrypoint.sh"]

FROM runtime AS evaluator

USER root

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y \
    -o APT::Install-Recommends=false \
    -o APT::Install-Suggests=false \
    ca-certificates \
    curl \
    procps

RUN mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
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

USER webserver

COPY --chown=webserver evaluator/entrypoint.sh /app/evaluator-entrypoint.sh

ENTRYPOINT ["/app/evaluator-entrypoint.sh"]
CMD ["rqworker", "default", "evaluator", "--with-scheduler"]
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pgrep -f "rqworker" || exit 1
