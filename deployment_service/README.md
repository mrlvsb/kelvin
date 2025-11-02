# Deployment Service

This directory contains the code for the Deployment Service, a FastAPI application that handles deployment requests from GitHub Actions. It validates incoming requests, performs deployments using Docker Compose, and manages rollbacks in case of failures.

## Setup & Development

Deployment service also as Kelvin uses `uv` for dependency management. To set up the development environment, follow these steps

1. Ensure you have `uv` installed as needed for the Kelvin project.

2. Create a virtual environment and install dependencies:
```bash
$ uv sync
```

3. Ensure you have `.env` file configured with necessary environment variables from the root of the Kelvin project. The needed variables are under the `# Deployment Service` section in the `.env.example` file.

4. Run the FastAPI application:
```bash
$ uv run fastapi dev --port 9000
```
The service will be accessible at `http://localhost:9000`.

5. To ensure that the code is formatted correctly and linted, you can install pre-commit hooks:
```bash
$ pre-commit install
```

We use `ruff` for linting and formatting. You can check and format the code using:
```bash
$ ruff check
$ ruff format
```

and `mypy` for type checking:
```bash
$ mypy .
```

## Deployment Service Overview

You can find a detailed description of the deployment workflow and architecture in the [Deployment Documentation](../docs/deployment.md).

## Deployment script

There is script that sends a deployment request to the deployment service endpoint.
It automatically takes care of signing, validation, and communication, so you don’t need to handle HMAC signatures or headers manually.

It works in both local environments and GitHub Actions.
When executed within a GitHub Actions workflow, it also generates a detailed Markdown report in the Job Summary, providing clear visibility into the deployment result.

No external dependencies are required — the script runs entirely on the Python standard library.

To view all available arguments, defaults, and examples, run:

```bash
python deploy.py --help
```
