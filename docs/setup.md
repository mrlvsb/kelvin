# Kelvin development
Kelvin has uses a relatively complicated set of runtime services, so you need to configure a bunch
of things to start using it.


## Installing dependencies
Firstly, install necessary system packages:

```bash
$ apt-get install libsasl2-dev libgraphviz-dev graphviz gcc libxml2-dev libxslt1-dev libffi-dev libz-dev python3-pip curl pre-commit
```

## Installing Python dependencies
Secondly, you need to prepare a Python virtual environment and install dependencies of Kelvin, which is
a Django app. The easiest way of doing that is to use [uv](https://github.com/astral-sh/uv),
which manages the dependencies of this project. As a first step for working
with the Python code, install `uv` using some [supported approach](https://docs.astral.sh/uv/getting-started/installation/), for example:

```bash
$ curl -LsSf https://astral.sh/uv/install.sh | sh
```
Then, use `uv` to create a virtual environment and install the necessary dependencies into it:
```bash
$ uv sync
```
> [!NOTE]
> If you have unsupported python version, use `uv python install 3.12` with following `uv sync --python 3.12`

If you want to work with Python scripts or start Django in this repository, simply prepend each such command with `uv run`:
```bash
$ uv run manage.py makemigrations
```

## Git pre-commit hooks
To ensure that the code is formatted correctly and linted, you can install pre-commit hooks:
```bash
$ pre-commit install
```

## Building the frontend
For building the frontend, you'll need `npm`:
```bash
$ cd frontend
$ npm ci
# Perform a production build:
$ npm run build
# Perform a development build with live-reload:
$ npm run dev
```
The frontend build will store JS and CSS files into `web/static`.

## Preparing the database
The web app needs a PostgreSQL database to run. You can either provide it yourself, or use the provided `docker-compose.yaml`
file (recommended).

### Running PostgreSQL with Docker
As a first step, you should configure an `.env` file that contains various environment
variables used to configure Kelvin and also `docker-compose`, which can be used to set up Kelvin
runtime services.

```bash
$ cp .env.example .env
```
You can modify the environment variables in the file to your liking.

Logged user need rights to work with docker.
```bash
$ sudo usermod -aG docker $USER
```
> [!WARNING]
> Do not forget logout and login to activate new rights.

Then, you can start a PostgreSQL database using `docker-compose`:
```bash
$ docker compose up db
```
> [!NOTE]
> Note that `docker compose` will load the DB (and other) configuration options from the `.env` file, same as Kelvin, so they should match.

### Running migrations
Once you have a working connection to the DB, you should run migrations on it:
```bash
$ uv run manage.py migrate
```

## Running the server
Once you built the frontend, installed Python dependencies and configured the database, you can start a local development server using this command:
```bash
$ uv run manage.py runserver 8000
```
And then you can find the web on `http://localhost:8000`.

## Deploying workers (optional)
To perform code plagiarism checks or evaluate code submits, you'll also need to deploy Redis and start RQ workers.

You can start Redis using the provided `docker-compose.yml` file:
```bash
$ docker compose up redis
```
> [!NOTE]
> Note that the Redis instance does not store data persistently.

You also need to compile the Docker images used for evaluation:
```bash
$ cd evaluator/images
$ uv run build.py
```

Then you can start a worker with the following command (in kelvin root folder):
```bash
$ uv run manage.py rqworker default evaluator --with-scheduler
```
## Initial setup
At first, let's create a superuser
```bash
(.venv) $ python3 manage.py createsuperuser
```
Ensure that local kelvin server and database is up, visit an admin page `<local_kelvin_url>/admin` and assign a group to admin, the name of the group is teacher.

## Database seeding

If you want to seed database with initial data, you can perform a command
```bash
(.venv) $ python3 manage.py initial_db_seed
```
A few students, subjects, teacher, semester and classes will be added.

