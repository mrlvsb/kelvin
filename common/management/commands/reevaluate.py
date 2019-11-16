from django.core.management.base import BaseCommand, CommandError
from common.models import Submit
import django_rq
from common.evaluate import evaluate_job

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--id', help='reevaluate submit by id')
        parser.add_argument('--failed', action='store_true', help='reevaluate all failed tasks')

    def handle(self, *args, **opts):
        failed = Submit.objects.filter(max_points=None)
        if opts['id']:
            failed = Submit.objects.filter(id=opts['id'])
        
        reevaluate = opts['id'] or opts['failed']

        print(failed.count())
        for s in failed:
            print(f"#{s.id} - {s}")

            if reevaluate:
                django_rq.enqueue(evaluate_job, s)