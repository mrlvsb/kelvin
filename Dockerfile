FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS build-backend

# Workaround for a timeouting VSB DNS. It seems that it is sadly unable to download APT packages
# from the default Debian mirror.
RUN sed -i "s#deb.debian.org/debian\$#ftp.debian.cz/debian#g" /etc/apt/sources.list.d/debian.sources

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update \
    -o Acquire::http::Timeout=10 \
    -o Acquire::https::Timeout=10 \
    -o Acquire::Retries=1 && \
    apt-get install -y \
    -o APT::Install-Recommends=false \
    -o APT::Install-Suggests=false \
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

FROM python:3.12-bookworm AS runtime

RUN sed -i "s#deb.debian.org/debian\$#ftp.debian.cz/debian#g" /etc/apt/sources.list.d/debian.sources

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update \
    -o Acquire::http::Timeout=10 \
    -o Acquire::https::Timeout=10 \
    -o Acquire::Retries=1 && \
    apt-get install -y \
    -o APT::Install-Recommends=false \
    -o APT::Install-Suggests=false \
    graphviz && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /app

# Create new user to run app process as unprivileged user
RUN groupadd --gid 102 webserver && \
    useradd --uid 101 --gid 102 --shell /bin/false --system webserver

RUN chown -R webserver:webserver .

COPY --from=build-backend --chown=webserver:webserver /app .
ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=webserver:webserver web ./web
COPY --chown=webserver:webserver kelvin ./kelvin
COPY --chown=webserver:webserver templates ./templates
COPY --chown=webserver:webserver evaluator ./evaluator
COPY --chown=webserver:webserver survey ./survey
COPY --chown=webserver:webserver common ./common
COPY --chown=webserver:webserver api ./api
COPY --chown=webserver:webserver manage.py .
COPY --from=build-frontend --chown=webserver:webserver /web/static/ ./web/static/

RUN mkdir -p /socket && chown webserver:webserver /socket

USER webserver

RUN python manage.py collectstatic --no-input --clear

COPY --chown=webserver:webserver deploy/entrypoint.sh ./

STOPSIGNAL SIGINT

ENTRYPOINT ["/app/entrypoint.sh"]
