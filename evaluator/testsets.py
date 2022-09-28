import io
import os
import shlex
import re
import traceback

import yaml

from .script import Script
from web.task_utils import load_readme
from kelvin.settings import BASE_DIR


class File:
    def __init__(self, path):
        self.path = path

    def open(self, mode='r'):
        if isinstance(self.path, io.BytesIO):
            if 'b' in mode:
                return io.BytesIO(self.path.getvalue())
            return io.StringIO(self.path.getvalue().decode('utf-8'))
        return open(self.path, mode)

    def size(self):
        if isinstance(self.path, io.BytesIO):
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

    def sorted_files(self):
        def sorter(item):
            name = item[0]
            f = item[1]

            if name == 'stdin':
                return (0, 'stdin')

            if f.input:
                return (1, name)

            if name == 'stdout':
                return (2, 'stdout')

            return (3, name)

        sorted_values = list(self.files.items())
        sorted_values.sort(key=sorter)
        return list(sorted_values)

    @title.setter
    def title(self, value):
        self._title = value

    def add_memory_file(self, name, input=False):
        f = io.BytesIO()
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
        if isinstance(self.file.path, io.BytesIO):
            return len(self.file.path.getvalue())
        return os.stat(self.file.path).st_size

    @property
    def path(self):
        return self.file.path

def parse_bool(value):
    if value in [True, 1, 'yes', 'on', 'enable', 'enabled']:
        return True
    if value in [False, 0, 'no', 'off', 'disable', 'disabled']:
        return False
    raise ValueError(f"Could not convert {value} to bool")


class TestSet:
    def __init__(self, task_path, meta=None):
        self.task_path = task_path
        self.meta = meta if meta else {}
        self.tests_dict = {}
        self.File = File
        self.warnings = []
        self.queue = 'evaluator'
        self.timeout = 180
        try:
            self.files_cache = os.listdir(self.task_path)
        except FileNotFoundError as e:
            self.add_warning(e)
            self.files_cache = []
        self.pipeline = []

        self.script = None
        if os.path.exists(os.path.join(self.task_path, 'script.py')):
            try:
                self.script = Script(self.task_path, self.meta, self.add_warning)
            except Exception as e:
                self.add_warning(f'script.py: {e}\n{traceback.format_exc()}')

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
        name = str(name)
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
            from . import pipelines
            counter = 1
            for item in conf:
                try:
                    pipe_type = item['type']
                    class_name = "".join([p.title() for p in re.split('_|-', item['type'])])
                    pipecls = getattr(pipelines, f"{class_name}Pipe", None)
                    if not pipecls and self.script:
                        pipecls = getattr(self.script.module, f"{class_name}Pipe", None)

                    args = {k: v for k, v in item.items() if k not in ['type', 'title', 'fail_on_error']}
                    if pipecls:
                        pipe = pipecls(**args)
                    else:
                        pipe = pipelines.DockerPipe(f'kelvin/{pipe_type}', **args)

                    pipe.type = pipe_type
                    pipe.title = item.get('title', item['type'])
                    pipe.fail_on_error = item.get('fail_on_error', True)

                    if not getattr(pipe, 'enabled', None):
                        pipe.enabled = True
                    if 'enabled' in item:
                        if item['enabled'] == 'announce':
                            pipe.enabled = 'announce'
                        else:
                            pipe.enabled = parse_bool(item['enabled'])

                    pipe.id = f"{counter:03}_{item['type']}"
                    counter += 1

                    self.pipeline.append(pipe)
                except Exception as e:
                    self.add_warning(f'pipe {item["type"]}: {e}\n{traceback.format_exc()}')

    def parse_conf_tests(self, conf):
        allowed_keys = ['name', 'title', 'exit_code', 'args', 'files']

        for test_conf in conf:
            t = self.create_test(test_conf.get('name', f'test {len(self.tests_dict)}'))
            t.title = test_conf.get('title', t.name)
            t.exit_code = test_conf.get('exit_code', 0)
            t.args = [str(s) for s in test_conf.get('args', [])]
            files = test_conf.get('files', [])
            for f in files:
                t.files[f['path']] = TestFile(File(os.path.join(self.task_path, f['expected'])))

            for k, v in test_conf.items():
                if k not in allowed_keys:
                    self.add_warning(f"task '{t.name}': unknown key '{k}'")

    def parse_conf_queue(self, conf):
        self.queue = conf

    def parse_conf_timeout(self, conf):
        self.timeout = conf

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

                with open(os.path.join(self.task_path, 'tests.yml')) as f:
                    tests = yaml.load(f.read(), Loader=yaml.SafeLoader)
                    if tests:
                        self.parse_conf_tests(tests)
        except yaml.scanner.ScannerError as e:
            self.add_warning(e)
        except FileNotFoundError:
            pass

        if self.script:
            self.script.call("gen_tests", self)

    def load_readme(self):
        try:
            task_relpath = os.path.relpath(self.task_path, os.path.join(BASE_DIR, "tasks"))
            vars = {}
            if self.script:
                vars = self.script.call('readme_vars', self)
            return load_readme(task_relpath, vars)
        except Exception as e:
            self.add_warning(f'script.py: {e}\n{traceback.format_exc()}')
