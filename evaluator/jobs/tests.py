import io
import logging
import os
import shlex
import subprocess
import tempfile
from datetime import timedelta
from typing import Any

from . import Job
from ..docker import ExecutionLimits, ExecutionLimitsUpdate, create_docker_cmd, prepare_docker_image
from ..evaluation import EvaluationContext, EvaluationPaths, File, TestFile
from ..results import EvaluationResult, TestResult
from ..utils import copyfile

logger = logging.getLogger(__name__)


DEFAULT_PER_TEST_TIMEOUT = timedelta(seconds=5)


class TestsJob(Job):
    def __init__(
        self,
        executable: str | list[str] = "./main",
        per_test_timeout: timedelta | None = None,
        before: list[str] | None = None,
        limits: ExecutionLimitsUpdate | None = None,
        image_name: str = "kelvin/run",
    ):
        self.executable = [executable] if isinstance(executable, str) else executable
        self.per_test_timeout = (
            per_test_timeout if per_test_timeout is not None else DEFAULT_PER_TEST_TIMEOUT
        )
        self.before = [] if not before else before
        self.limits = limits if limits is not None else ExecutionLimitsUpdate()
        self.image_name = image_name

    def run(self, paths: EvaluationPaths, ctx: EvaluationContext, result: EvaluationResult) -> Any:
        results = []
        os.mkdir(paths.result_dir)

        image = prepare_docker_image(self.image_name, self.before)

        container = (
            subprocess.check_output(
                create_docker_cmd(
                    paths,
                    image,
                    additional_args=["-d"],
                    # Limit to ensure that the container won't run too long
                    cmd=["sleep", str(ctx.config.timeout.total_seconds())],
                    custom_limits=self.limits,
                )
            )
            .decode("utf-8")
            .strip()
        )

        try:
            for test in ctx.tests:
                result = TestResult(paths.result_dir, {"name": test.name})

                # copy input files to the sandbox
                for path, f in test.files.items():
                    if f.input:
                        copyfile(f.path, os.path.join(paths.submit_dir, path))

                # run process in the sandbox
                cmd = self.executable + test.args

                with (
                    tempfile.NamedTemporaryFile() as stdout_name,
                    tempfile.NamedTemporaryFile() as stderr_name,
                ):
                    docker_cmd = [
                        "docker",
                        "exec",
                        "-i",
                        container,
                        "timeout",
                        str(self.per_test_timeout.total_seconds()),
                    ] + cmd
                    logger.debug(f"executing in isolation: `{shlex.join(docker_cmd)}`")

                    fsize = (
                        self.limits.fsize
                        if self.limits.fsize is not None
                        else ExecutionLimits.default().fsize
                    )

                    def preexec_fn():
                        """
                        Ensure that we apply the limit to the whole process, so that it is applied also
                        to produced stdout outside of the container.
                        """
                        import resource

                        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))

                    args = {}
                    if test.stdin:
                        stdin = test.stdin.open()
                        if isinstance(stdin, io.StringIO):
                            args["input"] = stdin.getvalue().encode("utf-8")
                        elif isinstance(stdin, io.BytesIO):
                            args["input"] = stdin.getvalue()
                        else:
                            args["stdin"] = stdin
                        result.copy_result_file("stdin", actual=test.stdin.file.path)

                    proc_result = subprocess.run(
                        docker_cmd,
                        **args,
                        stdout=stdout_name,
                        stderr=stderr_name,
                        preexec_fn=preexec_fn,
                    )
                    if "stdin" in args:
                        args["stdin"].close()

                    timeouted = proc_result.returncode == 124 and test.exit_code != 124
                    result["exit_code"] = proc_result.returncode

                    # copy all result and expected files
                    result.copy_result_file("stdout", actual=stdout_name.name, expected=test.stdout)
                    result.copy_result_file("stderr", actual=stderr_name.name, expected=test.stderr)
                    for path, expected in test.files.items():
                        if path in ["stdout", "stderr"]:
                            continue

                        if expected.input:
                            result.copy_input_file(path, expected)
                        else:
                            result.copy_result_file(
                                path,
                                actual=os.path.join(paths.submit_dir, path),
                                expected=expected,
                            )

                # do a comparison
                for name, opts in result.files.items():
                    if "expected" not in opts:
                        continue

                    msg = None
                    if "actual" not in opts:
                        opts["error"] = "file not found"
                        msg = f"file <strong>{name}</strong> not found"
                        if name == "stdout":
                            msg = "Standard output (<strong>stdout</strong>) is empty"
                        elif name == "stderr":
                            msg = "Standard error (<strong>stderr</strong>) is empty. Did you mean to use this?<pre><code class='c'>fprintf(stderr, \"message\\n\");</code></pre>"

                        opts["actual"] = TestFile(File(io.StringIO()))

                    success, output, diff = text_compare(opts["expected"].path, opts["actual"].path)
                    if output:
                        result.copy_html_result(name, output)
                    if diff:
                        result.copy_diff(name, diff)

                    if not msg:
                        msg = f"file <strong>{name}</strong> doesn't match"
                        if name == "stdout":
                            msg = "Standard output (<strong>stdout</strong>) doesn't match"
                        elif name == "stderr":
                            if opts["actual"].size() <= 0:
                                msg = "Standard error (<strong>stderr</strong>) is empty. Did you mean to use this?<pre><code class='c'>fprintf(stderr, \"message\\n\");</code></pre>"
                            else:
                                msg = "Standard error (<strong>stderr</strong>) doesn't match"
                    result.add_result(success, msg, output)

                if timeouted:
                    result.add_result(
                        success=False,
                        message=f"<strong>The test has timeouted after {self.per_test_timeout.total_seconds()}s</strong>. Make sure that you do not use e.g. `sleep` in your program.",
                    )
                elif test.exit_code is not None:
                    result.add_result(
                        test.exit_code == result["exit_code"],
                        f"<strong>main</strong> or <strong>exit</strong> function terminated the program with exit status <strong>{result['exit_code']}</strong> instead of <strong>{test.exit_code}</strong>",
                    )

                # save issued commandline
                result["command"] = " ".join(cmd)
                if "stdin" in args:
                    result["command"] += f" < {shlex.quote(os.path.basename(test.stdin.path))}"

                # run custom evaluation script
                if test.script:
                    check = getattr(test.script, "check", None)
                    if check:
                        custom_result = check(result, self)
                        if custom_result:
                            result.add_error(custom_result)

                results.append(result)
        finally:
            subprocess.Popen(["docker", "kill", container])

        return {
            "tests": results,
        }


# A hack which enables us to display a message if one of the files contains
# a newline at eof whilst the other does not
# This behaviour is accomplished by manually modifying the diff
# with_nl_message modifies the 'No newline at end of file' text by prefixing it
# with a + or - (depending on which file is missing the newline), and removing
# the leading backslash character
# Both of those transformations are necessary for diff2html to render our diff correctly
# Lastly, the function WILL NOT WORK without the '-u'/'--unified' flag
def with_nl_message(diff: str):
    split = diff.split("\n")

    try:
        idx = split.index("\\ No newline at end of file")
    except ValueError:
        return diff

    begin_char = "-" if split[idx - 1][0] == "-" else "+"
    split[idx] = f"{begin_char}<No newline at end of file>"

    return "\n".join(split)


def text_compare(expected, actual):
    def to_file(input):
        if isinstance(input, io.StringIO):
            f = tempfile.NamedTemporaryFile(mode="w")
            f.write(input.getvalue())
            return f.name
        return input

    try:
        expected = to_file(expected)
        actual = to_file(actual)

        cmd = [
            "diff",
            "-a",
            "-u",
            # "-i",
            # "-w",
            # '-B',
            actual,
            expected,
        ]

        with tempfile.TemporaryFile() as out:
            p = subprocess.Popen(cmd, stdout=out)
            p.communicate()

            success = p.returncode == 0

            out.seek(0)
            diff = out.read().decode("utf-8")
            diff = with_nl_message(diff)
            return success, None, diff
    except UnicodeDecodeError as e:
        return False, str(e), None
