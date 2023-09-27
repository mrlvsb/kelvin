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
$ ./evaluator/images/build.py  # Rerun if pipeline images changes
$ ./sync_from_prod.sh  # Optional, you can populate the db yourself
```
