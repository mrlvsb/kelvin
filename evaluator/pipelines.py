import json
import os
import io
import subprocess
import tempfile
import shlex
import hashlib
import logging
from common.utils import points_to_color
from .results import TestResult
from . import testsets

from .utils import parse_human_size, copyfile

logger = logging.getLogger('evaluator')

DEFAULT_LIMITS = {
    'fsize': '16M',
    'memory': '128M',
    'network': 'none'
}

IMAGE_LIMITS = {
    'kelvin/dotnet': {
        'network': 'bridge',
        'memory': '512M',
        'fsize': '128M',
    },
    'kelvin/cargo': {
        'network': 'bridge',
        'memory': '512M',
        'fsize': '128M',
    },
    'kelvin/java': {
        'network': 'bridge',
        'memory': '512M',
        'fsize': '128M',
    },
}


def create_docker_cmd(evaluation, image, additional_args=None, cmd=None, limits=None, env=None):
    if not limits:
        limits = {}
    limits = {**DEFAULT_LIMITS, **IMAGE_LIMITS.get(image.split(':')[0], {}), **limits}
    for (k, v) in limits.items():
        if k in ("fsize", "memory"):
            limits[k] = parse_human_size(v)

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

    network = limits["network"]
    # Forcefully disable using --network=host
    if network == "host":
        network = "bridge"
    return [
        'docker', 'run', '--rm',
        '--network', network,
        '-w', '/work',
        '-v', evaluation.submit_path + ':/work',
        '--ulimit', f'fsize={limits["fsize"]}:{limits["fsize"]}',
        '-m', str(limits['memory']),
        '--memory-swap', str(limits['memory']),
        '--user', str(os.getuid()),
        '-i',
        *additional_args,
        *env,
        image,
        *cmd,
    ]

def docker_image(name):
    parts = name.split(':')
    basename = parts[0]
    version = 'latest' if len(parts) == 1 else parts[1]
    return f'{basename}:{version}'

class ImageNotFoundException(Exception):
    pass

def prepare_container(name, before=None):
    if not before:
        return name

    hash = hashlib.md5((name + "\n".join(before)).encode('utf-8')).hexdigest()
    base_name = name.split(':')[0]
    target_name = f'{base_name}:{hash}'

    instructions = [f'FROM {name}'] + [f'RUN {cmd}' for cmd in before]

    logging.warning(f"Building image {target_name}")
    try:
        subprocess.check_output(["docker", "build", "-", "-t", target_name], input="\n".join(instructions), text=True, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        if 'pull access denied for' in e.output:
            raise ImageNotFoundException(name)
        raise Exception(e.output)
    return target_name


class DockerPipe:
    def __init__(self, image, limits=None, before=None, **kwargs):
        self.image = image
        self.kwargs = kwargs
        self.limits = limits
        self.before = [] if not before else before

    def run(self, evaluation):
        result_dir = os.path.join(evaluation.result_path, self.id)
        os.mkdir(result_dir)

        image = prepare_container(docker_image(self.image), self.before)
        args = create_docker_cmd(evaluation, image, env=self.kwargs, limits=self.limits)

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
        except FileNotFoundError:
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


# A hack which enables us to display a message if one of the files contains
# a newline at eof whilst the other does not
# This behaviour is accomplished by manually modifying the diff
# with_nl_message modifies the 'No newline at end of file' text by prefixing it
# with a + or - (depending on which file is missing the newline), and removing
# the leading backslash character
# Both of those transformations are necessary for diff2html to render our diff correctly
# Lastly, the function WILL NOT WORK without the '-u'/'--unified' flag
def with_nl_message(diff: str):
    split = diff.split('\n')

    try:
        idx = split.index('\\ No newline at end of file')
    except ValueError:
        return diff

    begin_char = '-' if split[idx-1][0] == '-' else '+'
    split[idx] = f'{begin_char}<No newline at end of file>'

    return '\n'.join(split)


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
            diff = out.read().decode('utf-8')
            diff = with_nl_message(diff)
            return success, None, diff
    except UnicodeDecodeError as e:
        return False, str(e), None


class TestsPipe:
    def __init__(self, executable='./main', limits=None, timeout=5, before=None, **kwargs):
        super().__init__(**kwargs)
        self.executable = [executable] if isinstance(executable, str) else executable
        self.limits = limits
        self.timeout = timeout
        self.before = [] if not before else before

    def run(self, evaluation):
        results = []
        result_dir = os.path.join(evaluation.result_path, self.id)
        os.mkdir(result_dir)

        image = prepare_container(docker_image('kelvin/run'), self.before)
        container = subprocess.check_output(create_docker_cmd(evaluation, image, additional_args=['-d'], cmd=['sleep', 300], limits=self.limits)).decode('utf-8').strip()
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
            cmd = self.executable + test.args

            with tempfile.NamedTemporaryFile() as stdout_name, tempfile.NamedTemporaryFile() as stderr_name:
                docker_cmd = ['docker', 'exec', '-i', container, 'timeout', str(self.timeout)] + cmd
                logger.debug("executing in isolation: %s",
                                " ".join(docker_cmd))  # TODO: shlex.join only in python3.8
                def preexec_fn():
                    import resource
                    fsize = parse_human_size(DEFAULT_LIMITS['fsize'])
                    resource.setrlimit(resource.RLIMIT_FSIZE, (fsize, fsize))
                p = subprocess.Popen(docker_cmd, **args, stdout=stdout_name, stderr=stderr_name, preexec_fn=preexec_fn)
                p.communicate(**comm_args)

                timeouted = p.returncode == 124 and test.exit_code != 124
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

            if timeouted:
                result.add_result(success=False,
                                  message=f"<strong>The test has timeouted after {self.timeout}s</strong>. Make sure that you do not use e.g. `sleep` in your program.")
            elif test.exit_code is not None:
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
        self.enabled = 'always'

    def run(self, evaluation):
        total = 0
        success = 0
        for action in evaluation.result.pipelines:
            if 'tests' in action:
                total += len(action['tests'])
                success += len(list(filter(lambda t: t['success'], action['tests'])))
            if action.get('failed', False):
                success = 0
                total = 0
                break

        max_points = evaluation.tests.meta['max_points']
        deadline = evaluation.tests.meta['deadline']
        is_after_deadline = deadline and deadline < evaluation.tests.meta['submitted_at']
        points = 0
        if total:
            points = round(success * max_points * (self.after_deadline_multiplier if is_after_deadline else 1) / total, 2)


        result = {
            "html": f"Kelvin {'proposes' if self.propose else 'assigned'} <span style='color: {points_to_color(points, max_points)}'>{points}</span> points from maximal {max_points} points."
        }

        if not self.propose:
            result['points'] = points
            result['points_overwrite'] = self.overwrite
        return result
