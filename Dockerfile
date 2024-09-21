FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS build-backend-stage

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

RUN --mount=type=cache,target=/root/.cache uv sync --frozen --no-dev --no-install-project --compile-bytecode

FROM node:22.9.0-bookworm-slim AS build-frontend-stage

WORKDIR /frontend

COPY frontend .

RUN mkdir -p /web/static

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
RUN groupadd --gid 1001 uvicorn && \
    useradd --uid 1001 --gid 1001 --shell /bin/false --system uvicorn

RUN chown -R uvicorn:uvicorn /app

COPY --from=build-backend-stage --chown=uvicorn:uvicorn /app .

ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=uvicorn:uvicorn kelvin ./kelvin

COPY --chown=uvicorn:uvicorn web ./web

COPY --from=build-frontend-stage --chown=uvicorn:uvicorn /web/static/frontend.css /web/static/frontend.js /web/static/dolos ./web/static/

COPY --chown=uvicorn:uvicorn templates ./templates

COPY --chown=uvicorn:uvicorn evaluator ./evaluator

COPY --chown=uvicorn:uvicorn survey ./survey

COPY --chown=uvicorn:uvicorn common ./common

COPY --chown=uvicorn:uvicorn api ./api

COPY --chown=uvicorn:uvicorn manage.py .

USER uvicorn

RUN python manage.py collectstatic --no-input

EXPOSE 8000

CMD ["uvicorn", "kelvin.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
