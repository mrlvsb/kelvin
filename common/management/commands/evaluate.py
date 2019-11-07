from django.core.management.base import BaseCommand, CommandError
from shutil import copyfile
from common.models import Submit
import json
from evaluator.evaluator import *

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('submit_file')

    def handle(self, *args, **opts):
        submit = Submit.objects.get(source=opts['submit_file'])

        tpl = "tasks/{}".format(submit.assignment.task.code)

        result = []

        sandbox = Sandbox()
        evaluation = Evaluation(tpl, sandbox)

        copyfile(submit.source.path, os.path.join(sandbox.path, "box/submit"))

        pipeline = [
            ('download', DownloadPipe()),
            ('normal run', GccPipeline()),
            ('run with sanitizer', GccPipeline(['-fsanitize=address', '-fsanitize=bounds', '-fsanitize=undefined'])),
            ('malloc fail tester', Mallocer()),
        ]
        
        for name, pipe in pipeline:
            res = pipe.run(evaluation)
            if res:
                result.append({'name': name, **res})
        
        submit.points = 0
        submit.max_points = 0
        for i in result:
            for test in i['tests']:
                if test['success']:
                    submit.points += 1
                submit.max_points += 1


        submit.result = json.dumps(result, indent=4)
        submit.save()