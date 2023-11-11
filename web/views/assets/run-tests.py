#!/usr/bin/python3

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# Usage: python3 run-tests.py <path-to-binary>
# Example: python3 run-tests.py ./main

CURRENT_DIR = Path(__file__).absolute().parent


def resolve_path(test_name: str, path: str) -> Path:
    return CURRENT_DIR / test_name / path


class Failure:
    pass


class WrongExitCode(Failure):
    def __init__(self, expected: int, actual: int):
        self.expected = expected
        self.actual = actual


class StreamMismatch(Failure):
    def __init__(self, stream: str, expected: Path, actual: Path):
        self.stream = stream
        self.expected = expected
        self.actual = actual


class OutputFileMissing(Failure):
    def __init__(self, name: str):
        self.name = name


class OutputFileMismatch(Failure):
    def __init__(self, name: str, expected: Path, actual: Path):
        self.name = name
        self.expected = expected
        self.actual = actual


def read_file(path: Path) -> str:
    with open(path) as f:
        return f.read()


def files_equal(file_a: Path, file_b: Path) -> bool:
    return read_file(file_a) == read_file(file_b)


def get_test_workdir(name: str) -> Path:
    return resolve_path(name, "workdir")


def relative_path(path: Path) -> Path:
    return path.relative_to(os.getcwd())


def calculate_diff(workdir: Path, name: str, expected: Path, actual: Path, indent: str) -> str:
    from difflib import unified_diff

    diff_path = workdir / f"{name}.diff"

    expected_lines = read_file(expected).splitlines(keepends=True)
    actual_lines = read_file(actual).splitlines(keepends=True)
    diff = "".join(
        unified_diff(expected_lines, actual_lines, fromfile=str(expected), tofile=str(actual)))
    with open(diff_path, "w") as diff_file:
        diff_file.write(diff)

    return f"""
{indent}Expected file: {relative_path(expected)}
{indent}Actual file: {relative_path(actual)}
{indent}Diff: {relative_path(diff_path)}"""


def run_test(
    binary: str,
    name: str,
    title: Optional[str] = None,
    args: Optional[List[str]] = None,
    stdin: Optional[str] = None,
    stdout: Optional[str] = None,
    stderr: Optional[str] = None,
    exit_code: int = 0,
    files_in: Optional[List[str]] = None,
    files_out: Optional[List[str]] = None
):
    workdir = get_test_workdir(name)
    shutil.rmtree(workdir, ignore_errors=True)
    os.makedirs(workdir, exist_ok=True)

    for file in files_in:
        shutil.copy(resolve_path(name, file), workdir)

    actual_stdout = workdir / "actual-stdout"
    actual_stderr = workdir / "actual-stderr"

    with open(actual_stdout, "wb") as stdout_file:
        with open(actual_stderr, "wb") as stderr_file:
            command = [binary] + args
            stdin_file = open(resolve_path(name, stdin),
                              "rb") if stdin is not None else subprocess.DEVNULL
            result = subprocess.run(
                command,
                stdin=stdin_file,
                stdout=stdout_file,
                stderr=stderr_file,
                cwd=workdir
            )

    if stderr is None and os.path.getsize(actual_stderr) == 0:
        os.unlink(actual_stderr)
    if stdout is None and os.path.getsize(actual_stdout) == 0:
        os.unlink(actual_stdout)
    if stdin is not None:
        stdin_file.close()

    # Check failures
    if result.returncode != exit_code:
        yield WrongExitCode(expected=exit_code, actual=result.returncode)

    def check_stream(path: Optional[str], actual: Path, stream: str):
        if path is not None:
            expected = resolve_path(name, stream)
            if not files_equal(actual, expected):
                yield StreamMismatch(stream=stream, expected=expected, actual=actual)

    yield from check_stream(stdout, actual_stdout, "stdout")
    yield from check_stream(stderr, actual_stderr, "stderr")

    for file in files_out:
        actual_file = workdir / file
        expected_file = resolve_path(name, file)
        if not actual_file.is_file():
            yield OutputFileMissing(file)
        elif not files_equal(actual_file, expected_file):
            yield OutputFileMismatch(file, expected=expected_file, actual=actual_file)


if len(sys.argv) < 2:
    print("Usage: python3 run-tests.py <path-to-binary>")
    exit(1)
binary = os.path.realpath(sys.argv[1])

tests = []
###GENERATED###

indent = " " * 4

passed = 0
for test in tests:
    failures = list(run_test(binary, **test))
    title = test.get("title", test["name"])
    label = f"Test {title}: "
    print(f"{label:<60}", end="")
    if len(failures) == 0:
        print("SUCCESS")
        passed += 1
    else:
        workdir = get_test_workdir(test["name"])

        print("FAILURE")
        for failure in failures:
            if isinstance(failure, WrongExitCode):
                print(
                    f"{indent}- Wrong exit code, expected {failure.expected}, actual {failure.actual}")
            elif isinstance(failure, OutputFileMissing):
                print(f"{indent}- Missing output file `{failure.name}`")
            elif isinstance(failure, OutputFileMismatch):
                diff = calculate_diff(workdir, failure.name, expected=failure.expected,
                                      actual=failure.actual, indent=indent + "  ")
                print(f"{indent}- Output file `{failure.name}` has wrong contents. {diff}")
            elif isinstance(failure, StreamMismatch):
                diff = calculate_diff(workdir, failure.stream, expected=failure.expected,
                                      actual=failure.actual, indent=indent + "  ")
                print(f"{indent}- `{failure.stream}` has wrong contents. {diff}")

total_tests = len(tests)

print()
print(f"Passed {passed}/{total_tests} test(s) ({(passed / total_tests) * 100.0:.0f} %)")
if passed == total_tests:
    print("All tests have passed")
else:
    print("Some tests have failed")
    exit(1)
