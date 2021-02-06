import json
import yaml
import os
import shlex
import html
from collections import defaultdict
import subprocess
import tempfile
from common.models import Submit
from common.utils import points_to_color 

class DockerPipe:
    def __init__(self, image, **kwargs):
        self.image = image
        self.kwargs = kwargs

    def run(self, evaluation):
        result_dir = os.path.join(evaluation.result_path, self.id)
        os.mkdir(result_dir)

        def fmt_value(v):
            if isinstance(v, list):
                return json.dumps(v)
            return v


        env = [f"-ePIPE_{k.upper()}={fmt_value(v)}" for k, v in self.kwargs.items()]
        template_path = os.path.abspath(os.path.join(evaluation.task_path, "template"))
        if os.path.isdir(template_path):
            env.append(f"-v{template_path}:/template:ro")

        args = [
            'docker', 'run', '--rm',
            '--network', 'none',
            '-w', '/work',
            '-v', evaluation.sandbox.system_path() + ':/work',
            *env,
            self.image
        ]

        def res_path(p):
            return os.path.join(result_dir, p)

        with open(res_path("stdout"), "w") as stdout, open(res_path("stderr"), "w") as stderr:
            p = subprocess.Popen(args, stdout=stdout, stderr=stderr)
            p.communicate()

        result = {}
        try:
            with open(os.path.join(evaluation.sandbox.system_path("piperesult.json"))) as f:
                result = json.load(f)
        except FileNotFoundError:
            pass

        if 'failed' not in result:
            result['failed'] = p.returncode != 0


        try:
            path = os.path.join(evaluation.sandbox.system_path("result.html"))
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
            exists = os.path.exists(evaluation.sandbox.system_path(f))
            result.append(f"<li class='text-{'success' if exists else 'danger'}'>{f}</li>")


        return {
            "html": f"<ul>{''.join(result)}</ul>"
        }

class TestsPipe:
    def __init__(self, executable='./main'):
        self.executable = executable

    def run(self, evaluation):
        results = []
        for test in evaluation.tests:
            results.append(evaluation.evaluate(self.id, test, self.executable))

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
