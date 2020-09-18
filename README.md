# Kelvin

Kelvin - The Ultimate Code Examinator

```
kelvin
├── api (deprecated? will be removed?)
├── evaluator (pipeline for evaluating, linting submits)
│   ├── images (docker images for custom pipeline actions)
│   └── pipelines.py (integrated pipeline actions - evaluating in isolate, ...)
├── kelvin (base configuration of the application)
├── examinator (real-time exams module without frontend)
├── survey (module for easy surveys defined in yaml)
└── web (web interface for the kelvin)
```


## Implementation

### Needed System Libraries

On Debian/Ubuntu:

```
libldap2-dev libsasl2-dev libcap-dev
```

## Start worker
```
$ ./manage.py rqworker
```

## Reevaluate a submit

```
./manage.py reevaluate --id <submit-id>
```

## Run testing evaluation
```
$ ./manage.py evaluate ./tasks/gaura/komb_05_strings/ ./submit.c
$ chromium /tmp/eval/result.html
```

### Favicon

Generated from [favicon.io](https://favicon.io/favicon-generator/) with Didact Gothic font.

## Importing students
Download 'Rozvrhove skupiny' from edison as html and run to import students according to their class:
```sh
$ ./manage.py import_students prezencni.html UPR 2020W
```

Ignore lectures and exercises and import all students to already existing class 'komb' in the current semester and subject:
```sh
$ ./manage.py import_students komb.html UPR 2020W --no-lectures --no-exercises --class-code komb
```
