# Kelvin development
Kelvin has uses a relatively complicated set of runtime services, so you need to configure a bunch
of things to start using it.

## Installing Python dependencies
First, you need to prepare a Python virtual environment and install dependencies of Kelvin, which is
a Django app. The easiest way of doing that is to use [uv](https://github.com/astral-sh/uv),
which manages the dependencies of this project. As a first step for working
with the Python code, install `uv` using some supported approach, for example:

```bash
$ pip install --user uv==0.4.4
```

Then, use `uv` to create a virtual environment and install the necessary dependencies into it:
```bash
$ uv sync
```

Do not forget to activate the virtual environment if you want to work with Python:
```bash
$ source .venv/bin/activate
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

Then, you can start a PostgreSQL database using `docker-compose`:
```bash
$ docker-compose up db
```

Note that `docker-compose` will load the DB (and other) configuration options from the `.env` file, same as Kelvin, so they should match.

### Running migrations
Once you have a working connection to the DB, you should run migrations on it:
```bash
(.venv) $ python3 manage.py migrate
```

## Running the server
Once you built the frontend, installed Python dependencies and configured the database, you can start a local development server using this command:
```bash
$ python3 manage.py runserver 8000
```
And then you can find the web on `http://localhost:8000`.

## Deploying workers (optional)
To perform code plagiarism checks or evaluate code submits, you'll also need to deploy Redis and start RQ workers.

You can start Redis using the provided `docker-compose.yml` file:
```bash
$ docker-compose up redis
```
Note that the Redis instance does not store data persistently.

You also need to compile the Docker images used for evaluation:
```bash
(.venv) $ cd evaluator/images
(.venv) $ python3 build.py
```

Then you can start a worker with the following command:
```bash
(.venv) $ python3 manage.py rqworker default evaluator --with-scheduler
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

