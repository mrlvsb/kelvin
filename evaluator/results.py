import os
import json
import shutil
import re
import io

from .testsets import File, TestFile
from .utils import copyfile


def encode_json(o):
    if isinstance(o, TestResult):
        return o.meta

    raise Exception(o)


class TestResult:
    def __init__(self, result_dir, meta=None):
        if not meta:
            meta = {}

        self.meta = {**{
            'success': True,
            'errors': []
        }, **meta}
        self.files = {}
        self.result_dir = result_dir

        self.aliases = {
            'stdin': 'in',
            'stdout': 'out',
            'stderr': 'err'
        }

    def discover_files(self):
        aliases = {v: k for k, v in self.aliases.items()}

        for file in os.listdir(self.result_dir):
            if not file.startswith(f"{self['name']}."):
                continue

            n = file[len(self['name'])+1:]
            base = re.sub(r'\.expected$', '', n)
            base = re.sub(r'^(file_in|html|diff)\.', '', base)
            base = aliases.get(base, base)

            if base not in self.files:
                self.files[base] = {}

            key = 'actual'
            if n.endswith('.expected'):
                key = 'expected'
            elif n.startswith('html'):
                key = 'html'
            elif n.startswith('diff'):
                key = 'diff'

            self.files[base][key] = TestFile(File(os.path.join(self.result_dir, file)))

            if n.startswith('file_in'):
                self.files[base][key].input = True

    def copy_input_file(self, local_name, real_file):
        if local_name == 'stdin':
            dst = 'in'
        else:
            dst = f"file_in.{local_name}"

        copyfile(
            real_file.path,
            os.path.join(self.result_dir, f"{self['name']}.{dst}")
        )

    def copy_html_result(self, name, content):
        with open(os.path.join(self.result_dir, f"{self['name']}.html.{name}"), 'w') as f:
            f.write(content)

    def copy_diff(self, name, content):
        with open(os.path.join(self.result_dir, f"{self['name']}.diff.{name}"), 'w') as f:
            f.write(content)

    def copy_result_file(self, name, expected=None, actual=None, force_save=False):
        ext = self.aliases.get(name, name)

        if expected:
            copyfile(
                expected.path, 
                os.path.join(self.result_dir, f"{self['name']}.{ext}.expected")
            )

        if actual:
            try:
                if isinstance(actual, File):
                    actual = actual.path
 
                dest = os.path.join(self.result_dir, f"{self['name']}.{ext}")
                if isinstance(actual, io.StringIO):
                    with open(dest, "w") as f:
                        f.write(actual.getvalue())
                elif os.stat(actual).st_size > 0 or expected:
                    shutil.copyfile(actual, dest)
            except FileNotFoundError:
                pass

        self.add_existing_file(name)

    def add_existing_file(self, name, error=None, type=None):
        self.files_cache = os.listdir(self.result_dir)
        result = {}

        def add_if_exists(key, real_name):
            if real_name in self.files_cache:
                result[key] = File(os.path.join(self.result_dir, real_name))

        add_if_exists('expected', f"{self['name']}.{self.aliases.get(name, name)}.expected")
        add_if_exists('actual', f"{self['name']}.{self.aliases.get(name, name)}")

        if error:
            result['error'] = error

        if type and result:
            result['type'] = type

        if result:
            self.files[name] = result

    def add_result(self, success, message, additional=None):
        if not success:
            self['errors'].append(message)
            self['success'] = False

    def add_error(self, message):
        self.add_result(False, message)

    def __getitem__(self, key):
        if key in self.files:
            return self.files[key]
        if key in self.meta:
            return self.meta[key]
        return getattr(self, key)

    def __setitem__(self, key, value):
        self.meta[key] = value

    def __getattr__(self, key):
        if key in self.files:
            return self.files[key]
        if key in self.meta:
            return self.meta[key]
        return None


class PipeResult:
    def __init__(self, id):
        self.id = id
        self.title = None
        self.html = None
        self.tests = []
        self.comments = {}
    
    def success(self):
        return len([t for t in self.tests if t.success])

    def total(self):
        return len(self.tests)

class EvaluationResult:
    def __init__(self, result_dir):
        self.result_dir = result_dir
        self.pipelines = []

        try:
            with open(os.path.join(self.result_dir, 'result.json')) as f:
                for pipe_json in json.load(f):
                    pipe = PipeResult(pipe_json.get('id', ''))
                    pipe.title = pipe_json.get('title', '')
                    pipe.html = pipe_json.get('html', '')
                    pipe.comments = pipe_json.get('comments', {})
                    pipe.failed = pipe_json.get('failed', False)
                    for test_json in pipe_json.get('tests', []):
                        result_dir = os.path.join(self.result_dir, pipe.id)

                        result = TestResult(result_dir, test_json)
                        result.discover_files()

                        pipe.tests.append(result)
                    self.pipelines.append(pipe)
        except FileNotFoundError:
            pass

    def save(self, path):
        with open(path, 'w') as f:
            json.dump(self.pipelines, f, indent=4, default=encode_json)

    def __iter__(self):
        return iter(self.pipelines)
