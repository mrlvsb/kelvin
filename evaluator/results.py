import os
import json

from .testsets import File


def encode_json(o):
    if isinstance(o, TestResult):
        return o.meta

    raise Exception(o)

class TestResult:
    def __init__(self, name, result_dir):
        self.meta = {
            'name': name,
            'success': True,
        }
        self.files = {}
        self.result_dir = result_dir

        self.__getattr__ = self.x__getattr__
        self.__setattr__ = self.x__setattr__
        

    @staticmethod
    def load(meta, result_dir):
        result = TestResult(meta['name'], result_dir)
        result.discover_files()
        return result

    def discover_files(self):
        def add_file_if_exists(key, path_suffix):
            path = os.path.join(self.result_dir, f"{self['name']}{path_suffix}")
            if os.path.exists(path):
                self.files[key] = File(path)

        add_file_if_exists('stdin', '.in')
        add_file_if_exists('stdout', '.out')
        add_file_if_exists('stdout_expected', '.out.expected')
        add_file_if_exists('stderr', '.err')
        add_file_if_exists('stderr_expected', '.err.expected')

    def __getitem__(self, key):
        if key in self.files:
            return self.files[key]
        if key in self.meta:
            return self.meta[key]
        return None

    def x__getattr__(self, key):
        raise 'x'

    def x__setattr__(self, key, v):
        raise 'y'
        

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
                        pipe.tests.append(TestResult.load(test_json, self.result_dir))
                    self.pipelines.append(pipe)
        except FileNotFoundError:
            pass

    def save(self, path):
        with open(path, 'w') as f:
            json.dump(self.pipelines, f, indent=4, default=encode_json)

    def __iter__(self):
        return iter(self.pipelines)