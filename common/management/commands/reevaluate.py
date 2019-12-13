from django.core.management.base import BaseCommand, CommandError
from django.db.models import Max, F

from common.models import Submit
import django_rq
from common.evaluate import evaluate_job

class Command(BaseCommand):
    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--id', help='reevaluate submit by id')
        group.add_argument('--failed', action='store_true', help='reevaluate all failed tasks')
        group.add_argument('--latest', action='store_true', help='reevaluate all latest submits for each student and task')
        group.add_argument('--all', action='store_true')
        parser.add_argument('--dry-run', action='store_true')

    def latest_submits(self):
        processed = set()
        for submit in Submit.objects.all().order_by('-submit_num'):
            key = (submit.student_id, submit.assignment_id)
            if key in processed:
                continue
            processed.add(key)
            yield submit

    def handle(self, *args, **opts):
        if opts['id']:
            submits = Submit.objects.filter(id=opts['id'])
        elif opts['latest']:
            submits = self.latest_submits()
        elif opts['failed']:
            submits = Submit.objects.filter(max_points=None)
        elif opts['all']:
            submits = Submit.objects.all()

        for s in submits:
            print(f"#{s.id} - {s}")

            if not opts['dry_run']:
                s.max_points = None
                s.points = None
                s.save()
                django_rq.enqueue(evaluate_job, s)