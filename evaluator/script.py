import importlib.util
import contextlib
import traceback
import os
import sys
import io
from typing import Any, Dict


@contextlib.contextmanager
def change_cwd(new_cwd):
    current = os.getcwd()
    os.chdir(new_cwd)
    try:
        yield
    finally:
        os.chdir(current)


class Script:
    def __init__(self, task_path: str, meta: Dict[str, Any], output_fn, filename="script.py"):
        self.task_path = task_path
        self.meta = meta
        self.output_fn = output_fn
        self.filename = filename
        self.module = None
        self.load_module()

    def load_module(self):
        module_name = "xyz"

        spec = importlib.util.spec_from_file_location(
            module_name, os.path.join(self.task_path, self.filename)
        )
        self.module = importlib.util.module_from_spec(spec)
        self.module.login = self.meta.get("login", None)
        self.module.meta = self.meta
        sys.modules[module_name] = self.module

        with self.sandbox_run():
            spec.loader.exec_module(self.module)

    def call(self, fn_name, *kargs, **kwargs):
        with self.sandbox_run():
            fn = getattr(self.module, fn_name, None)
            if fn:
                return fn(*kargs, **kwargs)

    @contextlib.contextmanager
    def sandbox_run(self):
        f = io.StringIO()
        with (
            contextlib.redirect_stdout(f),
            contextlib.redirect_stderr(f),
            change_cwd(self.task_path),
        ):
            try:
                yield
            except Exception as e:
                self.output_fn(f"script.py: {e}\n{traceback.format_exc()}")
        if f.getvalue():
            self.output_fn(f.getvalue())
