FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS build-backend

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y \
    -o APT::Install-Recommends=false \
    -o APT::Install-Suggests=false \
    libsasl2-dev \
    libgraphviz-dev \
    graphviz

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

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y \
    -o APT::Install-Recommends=false \
    -o APT::Install-Suggests=false \
    graphviz && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /app

# Create new user to run app process as unprivilaged user
RUN groupadd --gid 102 webserver && \
    useradd --uid 101 --gid 102 --shell /bin/false --system webserver

RUN chown -R webserver:webserver /app

COPY --from=build-backend --chown=webserver:webserver /app .
ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=webserver:webserver web ./web
COPY --from=build-frontend --chown=uvicorn:uvicorn /web/static/frontend.* ./web/static/
COPY --from=build-frontend --chown=uvicorn:uvicorn /web/static/dolos ./web/static/dolos
COPY --chown=webserver:webserver kelvin ./kelvin
COPY --chown=webserver:webserver templates ./templates
COPY --chown=webserver:webserver evaluator ./evaluator
COPY --chown=webserver:webserver survey ./survey
COPY --chown=webserver:webserver common ./common
COPY --chown=webserver:webserver api ./api
COPY --chown=webserver:webserver manage.py .

RUN mkdir -p /socket && chown webserver:webserver /socket

USER webserver

RUN python manage.py collectstatic --no-input --clear

EXPOSE 8000

COPY --chown=webserver:webserver deploy/entrypoint.sh ./
ENTRYPOINT [ "/app/entrypoint.sh" ]
STOPSIGNAL SIGINT
