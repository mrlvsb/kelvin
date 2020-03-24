# Kelvin

Kelvin - The Ultimate Code Examinator

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

## How to create a new task

1. Create a new directory in `/srv/kelvin/kelvin/tasks`.
2. Create `readme.md` and some input (small_numbers.in) and output (small_output.out) files.
3. Optionally create a configuration file `config.yml`.
4. Add a new Task record in admin (choose a name, ented directory).
5. Assign the task to a Class.


## Task options in `config.yml`

- filters:
  - TrailingSpaces - Removes spaces at the end of each line
  - Strip - stdout.strip()

## Reevaluate a submit

```
./manage.py reevaluate --id <submit-id>
```

## Run testing evaluation
```
$ ./manage.py evaluate ./tasks/gaura/komb_05_strings/ ./submit.c
$ chromium /tmp/eval/result.html
```

## Run evaluator tests
```
python -m evaluator.tests
```


### Favicon

Generated from [favicon.io](https://favicon.io/favicon-generator/) with Didact Gothic font.