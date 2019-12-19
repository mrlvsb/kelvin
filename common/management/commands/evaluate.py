import os

from django.core.management.base import BaseCommand, CommandError
from django.shortcuts import render

from evaluator.evaluator import evaluate, evaluate_score
from evaluator.testsets import TestSet
from web.views import render_markdown, highlight_code


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('task_dir', help='path to directory with the task')
        parser.add_argument('solution', help='path to source code in .c or tar')
        parser.add_argument('--print-json')

    def handle(self, *args, **opts):
        result = evaluate(opts['task_dir'], opts['solution'], '/tmp/eval')

        points, max_points = evaluate_score(result)
        r = render(None, 'web/task_detail.html', {
            'results': result,
            'text': render_markdown(opts['task_dir'], None),
            'inputs': TestSet(opts['task_dir'], {}),
            'source': highlight_code(opts['solution']),
            'task': {
                'name': os.path.basename(os.path.normpath(opts['task_dir']))
            },
            'submit': {
                'points': points,
                'max_points': max_points,
            }
        })
        with open('/tmp/eval/result.html', 'wb') as f:
            f.write(r.getvalue())
