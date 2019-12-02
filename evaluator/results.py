import os
import json

from .testsets import File

class TestResult:
    def __init__(self, meta):
        self.meta = meta

    def __getitem__(self, key):
        if key in self.meta:
            return self.meta[key]
        return None

    def __getattr__(self, key):
        if key in self.meta:
            return self.meta[key]
        return None

    def __setitem__(self, key, value):
        self.meta[key] = value

class PipeResult:
    def __init__(self, name, gcc):
        self.name = name
        self.gcc = gcc
        self.tests = []

class EvaluationResult:
    def __init__(self, result_dir):
        self.result_dir = result_dir
        self.pipelines = []

        try:
            with open(os.path.join(self.result_dir, 'result.json')) as f:
                for pipe_json in json.load(f):
                    pipe = PipeResult(pipe_json['name'], pipe_json['gcc'])
                    for test_json in pipe_json['tests']:
                        name = test_json['name']
                        test = TestResult(test_json)

                        def add_file_if_exists(key, path_suffix):
                            path = os.path.join(self.result_dir, f"{name}{path_suffix}")
                            if os.path.exists(path):
                                test[key] = File(path)

                        add_file_if_exists('stdin', '.in')
                        add_file_if_exists('stdout', '.out')
                        add_file_if_exists('stdout_expected', '.out.expected')
                        add_file_if_exists('stderr', '.err')
                        add_file_if_exists('stderr_expected', '.err.expected')

                        pipe.tests.append(test)

                    self.pipelines.append(pipe)



                    
        except FileNotFoundError:
            pass

    def __iter__(self):
        return iter(self.pipelines)