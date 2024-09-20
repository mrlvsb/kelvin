FROM python:3.12-bookworm AS build-backend-stage

RUN export DEBIAN_FRONTEND=noninteractive \
      && apt-get update \
      && apt-get install -y libsasl2-dev libgraphviz-dev graphviz

RUN pip install uv==0.4.12

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync

FROM node:22.9.0-bookworm-slim AS build-frontend-stage

WORKDIR /frontend

COPY frontend .

RUN mkdir -p /web/static

RUN ls -la

RUN npm run build

FROM python:3.12-bookworm AS runtime

RUN export DEBIAN_FRONTEND=noninteractive && \
      apt-get update && \
      apt-get install -y libsasl2-dev libgraphviz-dev graphviz

WORKDIR /app

COPY --from=build-backend-stage /app .

ENV PATH="/app/.venv/bin:$PATH"

COPY kelvin ./kelvin

COPY web ./web

COPY --from=build-frontend-stage /web/static/frontend.css /web/static/frontend.js /web/static/dolos ./web/static/

COPY templates ./templates

COPY evaluator ./evaluator

COPY survey ./survey

COPY common ./common

COPY api ./api

COPY manage.py .

# Create new user to run app process as unprivilaged user
RUN groupadd --gid 1001 uvicorn && \
      useradd --uid 1001 --gid 1001 --shell /bin/false --system uvicorn

RUN chown -R uvicorn:uvicorn /app

USER uvicorn

RUN python manage.py collectstatic --no-input

CMD ["uvicorn", "kelvin.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
EXPOSE 8000
