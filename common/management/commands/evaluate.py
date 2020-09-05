import os

from django.core.management.base import BaseCommand, CommandError
from django.shortcuts import render

from evaluator.evaluator import evaluate, evaluate_score
from evaluator.testsets import TestSet
from evaluator.results import EvaluationResult


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('task_dir', help='path to directory with the task')
        parser.add_argument('solution', help='path to source code in .c or tar')
        parser.add_argument('--print-json')

    def handle(self, *args, **opts):
        result_dir = '/tmp/eval'

        result = evaluate(opts['task_dir'], opts['solution'], result_dir)
        points, max_points = evaluate_score(result)

        # reread result so we get same state as in django
        result = EvaluationResult(result_dir)

        r = render(None, 'web/task_detail.html', {
            'results': result,
            'text': '',
            'inputs': TestSet(opts['task_dir'], {}),
            'source': '',
            'max_inline_content_bytes': 1024 * 50,
            'task': {
                'name': os.path.basename(os.path.normpath(opts['task_dir'])),
                'code': 'task'
            },
            'submit': {
                'id': 0,
                'assignment': {
                    'id': 0,
                },
                'student': {
                    'username': 'nobody',
                },
                'submit_num': 1,
                'points': points,
                'max_points': max_points,
            }
        })
        with open(os.path.join(result_dir, 'result.html'), 'wb') as f:
            f.write(r.getvalue())
