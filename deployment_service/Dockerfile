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

ENV PATH="/app/bin:$PATH"

RUN groupadd --gid 101 webserver && \
    useradd --uid 1000 --gid 101 --shell /bin/false --system webserver

COPY --from=build --chown=webserver:webserver /app /app

COPY --chown=webserver:webserver healthcheck.py /app/healthcheck.py

USER webserver

WORKDIR /app

# Test if the application can be imported
RUN <<EOT
python -Im site
python -Ic 'import app'
EOT

ENTRYPOINT [ "uvicorn" , "app.main:app", "--workers", "2", "--loop", "uvloop", "--host", "0.0.0.0" ]

CMD ["--port", "9000", "--root-path", "/deployment"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["python3", "/app/healthcheck.py"]
