# Kelvin

Kelvin - The Ultimate Code Examinator

```
kelvin
├── api
├── evaluator (pipeline for evaluating, linting submits)
│   ├── images (docker images for custom pipeline actions)
│   └── pipelines.py (integrated pipeline actions - Docker evaluation, ...)
├── kelvin (base configuration of the application)
├── survey (module for easy surveys defined in yaml)
└── web (web interface for the kelvin)
```

## Getting started

### Using docker

```shell-session
$ cp .env.example .env
$ docker-compose up
$ docker-compose exec web ./manage.py migrate
$ docker-compose exec web ./manage.py createsuperuser
$ ./evaluator/images/build.py  # Rerun if pipeline images change
$ ./sync_from_prod.sh  # Optional, you can populate the db yourself
```

## Development
This project is managed by [uv](https://github.com/astral-sh/uv). As a first step for working
with the Python code, install `uv` using some supported approach, e.g. `pip install uv==0.4.4`.

- Install dependencies into a virtual environment (which will be created for you):
    ```bash
    $ uv sync
    ```
- Lint & reformat Python code:
    ```bash
    $ ruff check
    $ ruff format
    ```

### Updating dependencies
1) Add a new Python dependency:
    ```bash
    $ uv add package==<version>
    ```
2) Update the legacy lockfile, which is used to synchronize packages with `pip` on production:
    ```bash
    $ uv export --format requirements-txt > requirements.txt
    ```
3) Commit the changes:
    ```bash
    $ git add pyproject.toml uv.lock requirements.txt
    ```
