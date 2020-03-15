import os

from django.core.management.base import BaseCommand
from django.conf import settings

from common.models import Task, Subject


class Command(BaseCommand):
    def handle(self, *args, **opts):
        tasks_dir = os.path.join(settings.BASE_DIR, 'tasks')

        for root, dirs, files in os.walk(tasks_dir):
            if 'readme.md' in files:
                relative_path = root[len(tasks_dir)+1:]
                with open(os.path.join(root, 'readme.md')) as f:
                    name = f.readline().strip('# \n')

                try:
                    abbr = relative_path.split('/')[0].upper()
                    subject = Subject.objects.get(abbr=abbr)

                    task, _ = Task.objects.get_or_create(code=relative_path, defaults={
                        'subject': subject
                    })
                    task.name = name
                    task.save()
                    print(relative_path)
                except Subject.DoesNotExist:
                    print(f"unknown subject: {abbr}")
