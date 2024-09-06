# Development

## Testing code
We currently do not have any tests :( But you can at least lint and reformat Python code using the
following commands:
```bash
$ ruff check
$ ruff format
```

## Updating dependencies
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

To update the version of an existing transitive dependency, you can use `uv lock --upgrade-package <package>=<version>`.
