FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS build-backend

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
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

RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && \
    apt-get install -y \
    -o APT::Install-Recommends=false \
    -o APT::Install-Suggests=false \
    graphviz && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

WORKDIR /app

# Create new user to run app process as unprivileged user
# We want to use ID 1000, to have the same ID as the default outside user
# And we also want group 101, to provide share access to the Unix uWSGI
# socket with the nginx image.
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
