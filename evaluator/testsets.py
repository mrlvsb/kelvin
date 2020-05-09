import io
import os
import shlex
import glob
import re
import sys
import importlib.util
import traceback
from collections import defaultdict

import yaml

from . import filters, pipelines
from .utils import parse_human_size
from web.task_utils import process_markdown
from kelvin.settings import BASE_DIR
from django.template import Context, Template


def load_module(path):
    module_name = "xyz"

    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class File:
    def __init__(self, path):
        self.path = path

    def open(self, mode='r'):
        if isinstance(self.path, io.StringIO):
            if 'b' in mode:
                return io.BytesIO(self.path.getvalue().encode('utf-8'))
            return io.StringIO(self.path.getvalue())
        return open(self.path, mode)

    def size(self):
        if isinstance(self.path, io.StringIO):
            return len(self.path.getvalue())
        return os.stat(self.path).st_size

    def read(self, mode='r'):
        with self.open(mode) as f:
            return f.read()

class Test:
    def __init__(self, name):
        self.name = name
        self.args = []
        self.exit_code = 0
        self.files = {}
        self.check = None
        self.filters = []
        self.limits = {}
        self._title = None
        self.script = None

    @property
    def stdin(self):
        if 'stdin' not in self.files:
            return None
        return self.files['stdin']

    @property
    def stdout(self):
        if 'stdout' not in self.files:
            return None
        return self.files['stdout']

    @property
    def stderr(self):
        if 'stderr' not in self.files:
            return None
        return self.files['stderr']

    @property
    def escaped_args(self):
        return " ".join(map(shlex.quote, self.args))

    @property
    def title(self):
        return self._title if self._title else self.name
    
    @title.setter
    def title(self, value):
        self._title = value

    def add_memory_file(self, name, input=False):
        f = io.StringIO()
        self.files[name] = TestFile(File(f), input=input)
        return f


class TestFile:
    def __init__(self, file, input=False):
        self.file = file
        self.input = input

    def open(self, mode='r'):
        return self.file.open(mode)

    def read(self, mode='r'):
        return self.file.read(mode)

    def size(self):
        if isinstance(self.file.path, io.StringIO):
            return len(self.file.path.getvalue())
        return os.stat(self.file.path).st_size

    @property
    def path(self):
        return self.file.path

class TestSet:
    def __init__(self, task_path, meta=None):
        self.task_path = task_path
        self.filters = []
        self.limits = {
            'wall-time': 0.5,
            'time': 0,
            'processes': 10,
            'stack': 0,
            'cg-mem': 5 * 1024 * 1024,
            'fsize': 1024, # in kbytes
        }
        self.meta = meta if meta else {}
        self.tests_dict = {}
        self.File = File
        self.comparators = {}
        self.warnings = []
        try:
            self.files_cache = os.listdir(self.task_path)
        except FileNotFoundError as e:
            self.add_warning(e)
            self.files_cache = []
        self.gcc_flags = []

        self.script = None
        path = os.path.join(self.task_path, 'script.py')
        if os.path.exists(path):
            try:
                self.script = load_module(path)
            except Exception as e:
                self.add_warning(f"script.py: {e}\n{traceback.format_exc()}")

        self.pipeline = []
        self.load_tests()

    def __iter__(self):
        return iter(sorted(self.tests_dict.values(), key=lambda t: t.name))

    @property
    def required_files(self):
        files = []
        for pipe in self.pipeline:
            if pipe.type == 'required_files':
                files += pipe.files
        return files

    def create_test(self, name):
        if name not in self.tests_dict:
            self.tests_dict[name] = Test(name)

        return self.tests_dict[name]

    def discover_tests(self):
        for f in self.files_cache:
            name = f.split('.')[0]
            path = os.path.join(self.task_path, f)

            n = f[len(name) + 1:]
            if n in ['in', 'out', 'err']:
                self.create_test(name).files['std' + n] = TestFile(File(path), n == 'in')

            parts = n.split('.', 1)
            if parts[0] == 'file_in':
                self.create_test(name).files[parts[1]] = TestFile(File(os.path.join(self.task_path, f)), True)
            elif parts[0] == 'file_out':
                self.create_test(name).files[parts[1]] = TestFile(File(os.path.join(self.task_path, f)), False)

    def add_warning(self, message):
        self.warnings.append(message)

    def parse_conf_pipeline(self, conf):
        if not isinstance(conf, list):
            self.add_warning('pipeline is not a list')
        else:
            counters = defaultdict(lambda: 0)
            for item in conf:
                try:
                    pipe_type = item['type']
                    class_name = "".join([p.title() for p in item['type'].split('_')])
                    pipecls = getattr(pipelines, f"{class_name}Pipe", None)
                    if not pipecls and self.script:
                        pipecls = getattr(self.script, f"{class_name}Pipe", None)

                    if not pipecls:
                        self.add_warning(f"Pipe {class_name}Pipe not exists")
                        continue

                    pipe = pipecls(**{k: v for k, v in item.items() if k not in ['type', 'title', 'fail_on_error']})
                    pipe.type = pipe_type
                    pipe.title = item.get('title', item['type'])
                    pipe.fail_on_error = item.get('fail_on_error', False)

                    pipe.id = f"{item['type']}_{counters[item['type']]}"
                    counters[pipe_type] += 1

                    self.pipeline.append(pipe)
                except Exception as e:
                    self.add_warning(f'pipe {item["type"]}: {e}\n{traceback.format_exc()}')


    def parse_conf_limits(self, conf):
        handlers = {
            'fsize': lambda txt: parse_human_size(txt) // 1024,
            'cg-mem': parse_human_size,
            'stack': parse_human_size,
        }

        for k, v in conf.items():
            if k not in self.limits.keys():
                self.add_warning(f'unknown limit {k}')
            else:
                try:
                    self.limits[k] = handlers.get(k, lambda txt: txt)(v)
                except ValueError as e:
                    self.add_warning(f'bad limit {k} value "{v}": {e}')

    def parse_conf_tests(self, conf):
        allowed_keys = ['name', 'title', 'exit_code', 'args', 'files']

        for test_conf in conf:
            t = self.create_test(str(test_conf.get('name', f'test {len(self.tests_dict)}')))
            t.title = test_conf.get('title', t.name)
            t.exit_code = test_conf.get('exit_code', 0)
            t.args = [str(s) for s in test_conf.get('args', [])]
            files = test_conf.get('files', [])
            for f in files:
                t.files[f['path']] = TestFile(File(os.path.join(self.task_path, f['expected'])))

            for k, v in test_conf.items():
                if k not in allowed_keys:
                    self.add_warning(f"task '{t.name}': unknown key '{k}'")


    def parse_conf_filters(self, conf):
        if not isinstance(conf, list):
            self.add_warning("Filters must be a list!")
            return

        for filter_name in conf:
            name = filter_name.lower()
            if name not in filters.all_filters:
                self.add_warning(f"Unknown filter: {name}, known filters are: {', '.join(filters.all_filters.keys())}")
            else:
                self.filters.append(filters.all_filters[name]())

    def parse_conf_comparators(self, conf):
        if not isinstance(conf, dict):
            self.add_warning("comparators must be a dict!")
            return

        # TODO: move creation of comparators here and check it
        for k, v in conf.items():
            self.comparators[k] = v

    def load_tests(self):
        self.discover_tests()

        try:
            with open(os.path.join(self.task_path, 'config.yml')) as f:
                conf = yaml.load(f.read(), Loader=yaml.SafeLoader)
                if conf:
                    for key, value in conf.items():
                        fn = getattr(self, f"parse_conf_{key}", None)
                        if not fn:
                            self.add_warning(f"Unknown configuration key: {key}")
                        else:
                            fn(value)
        except yaml.scanner.ScannerError as e:
            self.add_warning(e)
        except FileNotFoundError:
            pass

        if self.script:
            try:
                generate_tests = getattr(self.script, 'gen_tests', None)
                if generate_tests:
                    generate_tests(self)
            except Exception as e:
                self.add_warning(f"script.py: {e}\n{traceback.format_exc()}")

    def load_readme(self):
        try:
            tasks_dir = os.path.realpath(os.path.join(BASE_DIR, "tasks"))
            task_code = os.path.relpath(os.path.realpath(self.task_path), tasks_dir)
            with open(os.path.join(self.task_path, "readme.md")) as f:
                readme = f.read()
                if self.script:
                    fn = getattr(self.script, 'readme_vars', None)
                    if fn:
                        try:
                            t = Template(readme)
                            c = Context(fn(self))
                            readme = t.render(c)
                        except Exception as e:
                            self.add_warning(f"script.py: {e}\n{traceback.format_exc()}")

                return process_markdown(task_code, readme)
        except FileNotFoundError:
            pass
