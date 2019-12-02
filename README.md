# Kelvin

Kelvin - The Ultimate Code Examinator

## Implementation

### LDAP Howto

[LDAP VSB with Python](https://gist.github.com/geordi/2a0ba8609442618972cd17ed20e3242f)

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

1. Udelat novy adresar v /srv/kelvin/kelvin/tasks
2. Vytvorit readme.md a nejake vstupy (mala_cisla.in) a vystupy (mala_cisla.out)
3. Pripadne dalsi konfigurace je v config.yml ve stejnem adresari
4. Pak se vytvorit zaznam v tabulce Tasks (zvolit nazev, a nazev adresare)
5. Nasledne dany task priradit na cviceni

OPT: a obrazky se muzou davat treba do adresare figures

## Task options in `config.yml`

- filters:
  - TrailingSpaces - Removes spaces at the end of each line
  - Strip - stdout.strip()

## Reevaluate a submit

```
./manage.py reevaluate --id <submit-id>
```
