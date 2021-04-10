import json
import os
import io
import subprocess
import tempfile
import shlex
import logging
from common.utils import points_to_color
from .results import TestResult
from . import testsets

from .utils import parse_human_size, copyfile

logger = logging.getLogger('evaluator')


def create_docker_cmd(evaluation, image, additional_args=None, cmd=None, limits=None, env=None):
    if not limits:
        limits = {}
    limits = {
        'fsize': '16M',
        'memory': '128M',
        **limits
    }
    limits = {k: parse_human_size(v) for k, v in limits.items()}

    if not cmd:
        cmd = []

    cmd = [str(arg) for arg in cmd]

    if not env:
        env = {}

    if not additional_args:
        additional_args = []

    def fmt_value(v):
        if isinstance(v, list):
            return json.dumps(v)
        return v

    env = [f"-ePIPE_{k.upper()}={fmt_value(v)}" for k, v in env.items()]

    template_path = os.path.join("", evaluation.task_path, "template")
    if os.path.isdir(template_path):
        additional_args.append("-v")
        additional_args.append(f"{template_path}:/template:ro")

    return [
        'docker', 'run', '--rm',
        '--network', 'none',
        '-w', '/work',
        '-v', evaluation.submit_path + ':/work',
        '--ulimit', f'fsize={limits["fsize"]}:{limits["fsize"]}',
        '-m', str(limits['memory']),
        '--user', str(os.getuid()),
        *additional_args,
        *env,
        image,
        *cmd,
    ]



class DockerPipe:
    def __init__(self, image, limits=None, **kwargs):
        self.image = image
        self.kwargs = kwargs
        self.limits = limits

    def run(self, evaluation):
        result_dir = os.path.join(evaluation.result_path, self.id)
        os.mkdir(result_dir)

        args = create_docker_cmd(evaluation, self.image, env=self.kwargs, limits=self.limits)

        def res_path(p):
            return os.path.join(result_dir, p)

        with open(res_path("stdout"), "w") as stdout, open(res_path("stderr"), "w") as stderr:
            p = subprocess.Popen(args, stdout=stdout, stderr=stderr)
            p.communicate()        

        result = {}
        try:
            with open(os.path.join(evaluation.submit_path, "piperesult.json")) as f:
                result = json.load(f)
        except FileNotFoundError:
            pass

        with open(res_path("stdout")) as stdout, open(res_path("stderr")) as stderr:
            print(stdout.read())
            print(stderr.read())
            
        if 'failed' not in result:
            result['failed'] = p.returncode != 0


        try:
            path = os.path.join(evaluation.submit_path, "result.html")
            with open(path) as f:
                result['html'] = f.read()
            os.unlink(path)
        except FileNotFoundError as e:
            pass

        for f in ['stdout', 'stderr']:
            if os.path.getsize(res_path(f)) == 0:
                os.unlink(res_path(f))
        if not os.listdir(result_dir):
            os.rmdir(result_dir)

        return result

class RequiredFilesPipe:
    def __init__(self, files):
        self.files = files

    def run(self, evaluation):
        result = []
        for f in self.files:
            exists = os.path.exists(os.path.join(evaluation.submit_path, f))
            result.append(f"<li class='text-{'success' if exists else 'danger'}'>{f}</li>")


        return {
            "html": f"<ul>{''.join(result)}</ul>"
        }


def text_compare(expected, actual):
    def to_file(input):
        if isinstance(input, io.StringIO):
            f = tempfile.NamedTemporaryFile(mode='w')
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
            "-i",
            "-w",
            expected,
            actual,
        ]

        with tempfile.TemporaryFile() as out:
            p = subprocess.Popen(cmd, stdout=out)
            p.communicate()

            success = p.returncode == 0

            out.seek(0)
            return success, None, out.read().decode('utf-8')
    except UnicodeDecodeError as e:
        return False, str(e)


class TestsPipe:
    def __init__(self, executable='./main', limits=None, timeout=5, **kwargs):
        super().__init__(**kwargs)
        self.executable = executable
        self.limits = limits
        self.timeout = timeout

    def run(self, evaluation):
        results = []
        result_dir = os.path.join(evaluation.result_path, self.id)
        os.mkdir(result_dir)

        container = subprocess.check_output(create_docker_cmd(evaluation, 'kelvin/run', additional_args=['-d'], cmd=['sleep', 300], limits=self.limits)).decode('utf-8').strip()
        for test in evaluation.tests:
            result = TestResult(result_dir, {'name': test.name})

            # copy input files to the sandbox
            for path, f in test.files.items():
                if f.input:
                    copyfile(f.path, os.path.join(evaluation.submit_path, path))

            args = {}
            comm_args = {}
            have_file_stdin = False
            if test.stdin:
                stdin = test.stdin.open()
                if isinstance(stdin, io.StringIO):
                    comm_args['input'] = stdin.getvalue().encode('utf-8')
                    args['stdin'] = subprocess.PIPE
                else:
                    args['stdin'] = stdin
                    have_file_stdin = True
                result.copy_result_file('stdin', actual=test.stdin.file.path)

            # run process in the sandbox
            cmd = [self.executable] + test.args

            with tempfile.NamedTemporaryFile() as stdout_name, tempfile.NamedTemporaryFile() as stderr_name:
                isolate_cmd = shlex.split(f"docker exec -i {container}") + ['timeout', str(self.timeout)] + cmd
                logger.debug("executing in isolation: %s",
                                " ".join((isolate_cmd)))  # TODO: shlex.join only in python3.8
                p = subprocess.Popen(isolate_cmd, **args, stdout=stdout_name, stderr=stderr_name)
                p.communicate(**comm_args)

                result['exit_code'] = p.returncode

                if have_file_stdin:
                    args['stdin'].close()

                # copy all result and expected files
                result.copy_result_file('stdout', actual=stdout_name.name, expected=test.stdout)
                result.copy_result_file('stderr', actual=stderr_name.name, expected=test.stderr)
                for path, expected in test.files.items():
                    if path in ['stdout', 'stderr']:
                        continue

                    if expected.input:
                        result.copy_input_file(path, expected)
                    else:
                        result.copy_result_file(path, actual=os.path.join(evaluation.submit_path, path), expected=expected)

            # do a comparsion
            for name, opts in result.files.items():
                if 'expected' not in opts:
                    continue

                msg = None
                if 'actual' not in opts:
                    opts['error'] = 'file not found'
                    msg = f"file <strong>{name}</strong> not found"
                    if name == 'stdout':
                        msg = "Standard output (<strong>stdout</strong>) is empty"
                    elif name == 'stderr':
                        msg = "Standard error (<strong>stderr</strong>) is empty. Did you mean to use this?<pre><code class='c'>fprintf(stderr, \"message\\n\");</code></pre>"

                    opts['actual'] = testsets.TestFile(testsets.File(io.StringIO()))

                success, output, diff = text_compare(opts['expected'].path, opts['actual'].path)
                if output:
                    result.copy_html_result(name, output)
                if diff:
                    result.copy_diff(name, diff)

                if not msg:
                    msg = f"file <strong>{name}</strong> doesn't match"
                    if name == 'stdout':
                        msg = "Standard output (<strong>stdout</strong>) doesn't match"
                    elif name == 'stderr':
                        if opts['actual'].size() <= 0:
                            msg = "Standard error (<strong>stderr</strong>) is empty. Did you mean to use this?<pre><code class='c'>fprintf(stderr, \"message\\n\");</code></pre>"
                        else:
                            msg = "Standard error (<strong>stderr</strong>) doesn't match"
                result.add_result(success, msg, output)

            if test.exit_code is not None:
                result.add_result(test.exit_code == result['exit_code'],
                                  f"<strong>main</strong> or <strong>exit</strong> function terminated the program with exit status <strong>{result['exit_code']}</strong> instead of <strong>{test.exit_code}</strong>")

            # save issued commandline
            result['command'] = ' '.join(cmd)
            if have_file_stdin:
                result['command'] += f' < {shlex.quote(os.path.basename(test.stdin.path))}'

            # run custom evaluation script
            if test.script:
                check = getattr(test.script, 'check', None)
                if check:
                    custom_result = check(result, self)
                    if custom_result:
                        result.add_error(custom_result)

            results.append(result)

        subprocess.Popen(["docker", "stop", container])

        return {
            "tests": results,
        }

class SleepPipe:
    def __init__(self, seconds=1):
        self.seconds = seconds

    def run(self, evaluation):
        import time
        time.sleep(self.seconds)

class AutoGraderPipe:
    def __init__(self, propose=False, after_deadline_multiplier=0, overwrite=False):
        self.propose = propose
        self.after_deadline_multiplier = max(0, min(1.0, after_deadline_multiplier))
        self.overwrite = overwrite

    def run(self, evaluation):
        if 'submit_id' not in evaluation.tests.meta:
            return

        total = 0
        success = 0
        for action in evaluation.result.pipelines:
            if 'tests' in action:
                total += len(action['tests'])
                success += len(list(filter(lambda t: t['success'], action['tests'])))

        if total <= 0:
            return

        s = Submit.objects.get(id=evaluation.tests.meta['submit_id'])
        is_after_deadline = s.assignment.deadline and s.assignment.deadline < s.created_at
        points = round(success * s.assignment.max_points * (self.after_deadline_multiplier if is_after_deadline else 1) / total, 2)

        if self.propose:
            return {
                "html": f"Kelvin proposes <span style='color: {points_to_color(points, s.assignment.max_points)}'>{points}</span> points from maximal {s.assignment.max_points} points."
            }
        else:
            if (s.assigned_points is not None and self.overwrite) or s.assigned_points is None:
                s.assigned_points = points
                s.save()
