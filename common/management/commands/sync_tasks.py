import os

from django.core.management.base import BaseCommand
from django.conf import settings

from common.models import Task, Subject
from web.task_utils import load_readme 


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('dir', nargs='?')

    def handle(self, *args, **opts):
        tasks_dir = os.path.realpath(os.path.join(settings.BASE_DIR, 'tasks'))

        if not opts['dir']:
            target_dir = tasks_dir
        else:
            target_dir = os.path.realpath(opts['dir'])

        x = os.path.relpath(target_dir, tasks_dir)

        for root, dirs, files in os.walk(target_dir):
            if 'readme.md' in files:
                relative_path = os.path.relpath(root, tasks_dir)
                readme = load_readme(relative_path)

                try:
                    abbr = relative_path.split('/')[0].upper()
                    subject = Subject.objects.get(abbr=abbr)

                    task, _ = Task.objects.get_or_create(code=relative_path, defaults={
                        'subject': subject
                    })
                    task.name = readme.name
                    task.announce = True if readme.announce else False
                    task.save()
                    print(relative_path)
                except Subject.DoesNotExist:
                    print(f"unknown subject: {abbr}")
