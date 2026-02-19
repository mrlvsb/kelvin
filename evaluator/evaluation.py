import dataclasses
import io
import os
import shlex
import re
import traceback
from typing import Any, Dict, Optional

import yaml
import serde

from .script import Script
from web.markdown_utils import load_readme
from kelvin.settings import BASE_DIR


class File:
    def __init__(self, path):
        self.path = path

    def open(self, mode="r"):
        if isinstance(self.path, io.BytesIO):
            if "b" in mode:
                return io.BytesIO(self.path.getvalue())
            return io.StringIO(self.path.getvalue().decode("utf-8"))
        return open(self.path, mode)

    def size(self):
        if isinstance(self.path, io.BytesIO):
            return len(self.path.getvalue())
        return os.stat(self.path).st_size

    def read(self, mode="r"):
        with self.open(mode) as f:
            return f.read()


class Test:
    def __init__(self, name):
        self.name = name
        self.args = []
        self.exit_code = 0
        self.pos = 99
        self.files = {}
        self.check = None
        self._title = None
        self.script = None

    @property
    def stdin(self):
        if "stdin" not in self.files:
            return None
        return self.files["stdin"]

    @property
    def stdout(self):
        if "stdout" not in self.files:
            return None
        return self.files["stdout"]

    @property
    def stderr(self):
        if "stderr" not in self.files:
            return None
        return self.files["stderr"]

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

            if name == "stdin":
                return 0, "stdin"

            if f.input:
                return 1, name

            if name == "stdout":
                return 2, "stdout"

            return 3, name

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
    def __init__(self, file: File, input=False):
        self.file = file
        self.input = input

    def open(self, mode="r"):
        return self.file.open(mode)

    def read(self, mode="r"):
        return self.file.read(mode)

    def size(self):
        if isinstance(self.file.path, io.BytesIO):
            return len(self.file.path.getvalue())
        return os.stat(self.file.path).st_size

    @property
    def path(self):
        return self.file.path


class EvaluationContext:
    """
    Context for evaluating submits of a given task.

    The context is loaded from a task directory, and it may contain:
    - config.yml: defines the individual jobs of the evaluation workflow
    - tests.yml: defines tests which should be executed when running the `tests` job
    - test files: those are automatically detected and added to the test set
    - script.py: custom Python script that can generate custom tests and provide variables for
      readme.md
    - readme.md: task README which can be enhanced by script.py
    """

    def __init__(self, task_path: str, meta: Optional[Dict[str, Any]] = None):
        """
        - `task_path` is a task directory
        - `meta` contains additional metadata which is passed to script.py when evaluating dynamic
            context data.
        """
        self.task_path = task_path

        # Note: the meta attribute is used a lot by existing `script.py` files
        # It should not be removed or moved.
        self.meta = meta if meta else {}
        self.warnings = []

        try:
            config_result = WorkflowConfig.parse(os.path.join(task_path, "config.yml"))
            self.config = config_result.config
            for key in config_result.unknown_keys:
                self.add_warning(f"Unknown config.yml key `{key}`")
        except WorkflowValidationError as e:
            self.config = WorkflowConfig(tests=[], jobs=[])
            self.add_warning(e)

        # First, load statically known tests
        test_config = TestConfig.parse(os.path.join(task_path, "tests.yml"))
        self.tests_dict = load_tests(self.config, test_config)
        self.pipeline = self.config.jobs

        self.script = None
        if os.path.exists(os.path.join(self.task_path, "script.py")):
            try:
                self.script = Script(self.task_path, self.meta, self.add_warning)

                # Then enrich tests using a dynamic script, if present
                self.script.call("gen_tests", self)
            except Exception as e:
                self.add_warning(f"script.py: {e}\n{traceback.format_exc()}")

        # And finally discover test files
        record_test_files(self.tests_dict, task_path)

        # And renumber all tests
        for pos, test in enumerate(self.tests_dict.values()):
            test.pos = pos

    def __iter__(self):
        return iter(sorted(self.tests_dict.values(), key=lambda t: (t.pos, t.name)))

    @property
    def queue(self) -> str:
        return self.config.queue

    @property
    def timeout(self) -> int:
        return self.config.timeout

    @property
    def required_files(self):
        files = []
        for pipe in self.pipeline:
            if pipe.type == "required_files":
                files += pipe.files
        return files

    def create_test(self, name: str) -> Test:
        """
        Get or create an existing test.
        Note: this function is used a lot in existing `script.py` files.
        Its signature should not be changed.
        """
        name = str(name)
        if name not in self.tests_dict:
            self.tests_dict[name] = Test(name)

        return self.tests_dict[name]

    def add_warning(self, message):
        self.warnings.append(message)

    def load_readme(self):
        try:
            task_relpath = os.path.relpath(self.task_path, os.path.join(BASE_DIR, "tasks"))
            vars = {}
            if self.script:
                vars = self.script.call("readme_vars", self)
            return load_readme(task_relpath, vars)
        except Exception as e:
            self.add_warning(f"script.py: {e}\n{traceback.format_exc()}")


@dataclasses.dataclass()
class TestDefinition:
    name: str
    title: str
    exit_code: int
    args: list[str]


# TODO: make this into something better :)
WorflowJob = Any


@dataclasses.dataclass()
class WorkflowConfig:
    """
    Represents config stored in config.yml.
    It configures various options for evaluating a submit.
    """

    tests: list[TestDefinition]
    jobs: list[WorflowJob]
    queue: str = "evaluator"
    timeout: int = 180

    @staticmethod
    def parse(config_path: str) -> "WorkflowConfigParseResult":
        queue = "evaluator"
        timeout = 180
        tests = {}
        jobs = []
        unknown_keys: list[str] = []
        ignored_keys = {"async"}

        try:
            with open(config_path) as f:
                conf = yaml.load(f.read(), Loader=yaml.SafeLoader)
                if conf:
                    for key, value in conf.items():
                        if key == "queue":
                            queue = value
                        elif key == "timeout":
                            timeout = value
                        elif key == "tests":
                            tests = parse_config_tests(value)
                        elif key == "pipeline":
                            jobs = parse_config_jobs(value)
                        elif key not in ignored_keys:
                            unknown_keys.append(key)
        except FileNotFoundError:
            pass
        return WorkflowConfigParseResult(
            config=WorkflowConfig(queue=queue, timeout=timeout, tests=tests, jobs=jobs),
            unknown_keys=unknown_keys,
        )


@dataclasses.dataclass()
class WorkflowConfigParseResult:
    config: WorkflowConfig
    unknown_keys: list[str] = dataclasses.field(default_factory=list)


def parse_config_tests(value: list[Any]) -> list[TestDefinition]:
    """
    Parse workflow tests, either from `tests:` field in `config.yml` or from a `tests.yml` file.
    """

    @serde.serde(deny_unknown_fields=True)
    class TestDefinitionYaml:
        name: Optional[str] = None
        title: Optional[str] = None
        exit_code: int = 0
        args: list[Any] = dataclasses.field(default_factory=list)

    tests = []
    for test in value:
        test = serde.from_dict(TestDefinitionYaml, test)
        name = test.name if test.name is not None else len(tests)
        title = test.title if test.title is not None else name
        args = [str(arg) for arg in test.args]
        tests.append(
            TestDefinition(
                name=name,
                title=title,
                exit_code=test.exit_code,
                args=args,
            )
        )
    return tests


class WorkflowValidationError(BaseException):
    pass


def parse_config_jobs(value: list[Any]) -> list[WorflowJob]:
    if not isinstance(value, list):
        raise WorkflowValidationError("Pipeline has to be a list of jobs")
    else:
        from . import pipelines

        jobs = []

        counter = 1
        for item in value:
            try:
                pipe_type = item["type"]
                class_name = "".join([p.title() for p in re.split("_|-", item["type"])])
                pipecls = getattr(pipelines, f"{class_name}Pipe", None)

                args = {
                    k: v for k, v in item.items() if k not in ["type", "title", "fail_on_error"]
                }
                if pipecls:
                    pipe = pipecls(**args)
                else:
                    pipe = pipelines.DockerPipe(f"kelvin/{pipe_type}", **args)

                pipe.type = pipe_type
                pipe.title = item.get("title", item["type"])
                pipe.fail_on_error = item.get("fail_on_error", True)

                if not getattr(pipe, "enabled", None):
                    pipe.enabled = True
                if "enabled" in item:
                    if item["enabled"] == "announce":
                        pipe.enabled = "announce"
                    else:
                        pipe.enabled = parse_bool(item["enabled"])

                pipe.id = f"{counter:03}_{item['type']}"
                counter += 1

                jobs.append(pipe)
            except Exception as e:
                raise WorkflowValidationError(f"pipe {item['type']}: {e}\n{traceback.format_exc()}")
        return jobs


def parse_bool(value):
    if value in [True, 1, "yes", "on", "enable", "enabled"]:
        return True
    if value in [False, 0, "no", "off", "disable", "disabled"]:
        return False
    raise ValueError(f"Could not convert {value} to bool")


@dataclasses.dataclass()
class TestConfig:
    """
    Test config stored in tests.yml.
    It configures tests for the `tests` job.
    """

    tests: list[TestDefinition]

    @staticmethod
    def parse(path: str) -> "TestConfig":
        tests = []

        try:
            with open(path) as f:
                conf = yaml.load(f.read(), Loader=yaml.SafeLoader)
                if conf:
                    tests = parse_config_tests(conf)
        except FileNotFoundError:
            pass
        return TestConfig(tests=tests)


def load_tests(config: WorkflowConfig, test_config: TestConfig) -> Dict[str, Test]:
    tests: Dict[str, Test] = {}

    def update_test(test: Test, test_def: TestDefinition):
        test.title = test_def.title
        test.exit_code = test_def.exit_code
        test.args = test_def.args

    # First, add tests loaded from the main config
    for test_def in config.tests:
        test = Test(name=test_def.name)
        update_test(test, test_def)
        tests[test.name] = test

    # Then add tests from the test config
    for test_def in test_config.tests:
        name = test_def.name
        if name in tests:
            test = tests[name]
        else:
            test = Test(name=name)
        update_test(test, test_def)
        tests[name] = test

    return tests


def record_test_files(tests: Dict[str, Test], task_path: str):
    try:
        files = os.listdir(task_path)
    except FileNotFoundError:
        return

    def get_test(name: str) -> Test:
        if name in tests:
            return tests[name]
        test = Test(name=name)
        tests[name] = test
        return test

    for f in files:
        name = f.split(".")[0]
        path = os.path.join(task_path, f)

        n = f[len(name) + 1 :]
        if n in ["in", "out", "err"]:
            get_test(name).files["std" + n] = TestFile(File(path), n == "in")

        parts = n.split(".", 1)
        if parts[0] == "file_in":
            get_test(name).files[parts[1]] = TestFile(File(os.path.join(task_path, f)), True)
        elif parts[0] == "file_out":
            get_test(name).files[parts[1]] = TestFile(File(os.path.join(task_path, f)), False)
