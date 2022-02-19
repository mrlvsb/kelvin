# Kelvin

Kelvin - The Ultimate Code Examinator

```
kelvin
├── api
├── evaluator (pipeline for evaluating, linting submits)
│   ├── images (docker images for custom pipeline actions)
│   └── pipelines.py (integrated pipeline actions - evaluating in isolate, ...)
├── kelvin (base configuration of the application)
├── examinator (real-time exams module without frontend)
├── survey (module for easy surveys defined in yaml)
└── web (web interface for the kelvin)
```

## Getting started

### Using docker

```shell-session
$ cp .env.example .env
$ docker-compose up -d
$ docker-compose exec web ./manage.py migrate
$ docker-compose exec web ./manage.py createsuperuser
```

### Native setup
- install docker
```shell-session
$ sudo apt install python3 python3-virtualenv libldap2-dev libsasl2-dev pandoc
$ virtualenv -p python3 venv
$ source venv/bin/activate
$ pip3 install -r requirements.txt # rerun if somebody changes requirements.txt
$ (cd frontend/ && npm install) # rerun if somebody changes frontend/package.json
$ ./sync_from_prod.sh # create psql container from production db, download all submits and tasks
$ ./evaluator/images/build.py # rerun if pipeline images changes
```

### Start
```shell-session
$ docker start kelvin_pgsql # rerun ./sync_from_prod.sh if not exists
$ ./manage.py runserver
$ (cd frontend && npm run dev) # watch & build frontend
$ ./manage.py rqworker evaluator # start evaluator worker
```
