import os
import re

from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth.models import User

from common.models import Task, Subject, AssignedTask, Class, Submit
from web.task_utils import load_readme 

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('dir', nargs='?')
        parser.add_argument('--delete-missing', help='Remove tasks that no longer exists on FS. Only tasks without submits are removed', choices=['empty', 'with_submits'], nargs='?', const='empty')

    def handle(self, *args, **opts):
        tasks_dir = os.path.realpath(os.path.join(settings.BASE_DIR, 'tasks'))

        if opts['delete_missing']:
            for task in Task.objects.all():
                fullpath = os.path.join(tasks_dir, task.code)
                if not os.path.isdir(fullpath):
                    print(task.code)
                    delete = opts['delete_missing'] == 'with_submits'

                    if not delete:
                        assigned_ids = AssignedTask.objects.filter(task_id=task.id).values_list('id', flat=True)
                        submits = Submit.objects.filter(assignment_id__in=assigned_ids)
                        delete = len(submits) == 0

                    if delete:
                        task.delete()
                        print("deleted")
                    else:
                        print("not deleted")

        if not opts['dir']:
            target_dir = tasks_dir
        else:
            target_dir = os.path.realpath(opts['dir'])

        for root, dirs, files in os.walk(target_dir):
            if '.git' in root:
                continue
            relative_path = os.path.relpath(root, tasks_dir)
            readme = load_readme(relative_path)
            if not readme:
                continue
            print(relative_path)

            try:
                parts = relative_path.split('/')

                abbr = parts[0].upper()
                subject = Subject.objects.get(abbr=abbr)

                taskid_path = os.path.join(root, ".taskid")

                search = {}
                try:
                    with open(taskid_path) as f:
                        search['id'] = int(f.read())
                except:
                    search['code'] = relative_path

                task, _ = Task.objects.get_or_create(**search, defaults={
                    'subject': subject
                })
                task.code = relative_path
                task.name = readme.name
                task.announce = True if readme.announce else False
                task.save()

                if 'id' not in search:
                    with open(taskid_path, 'w') as f:
                        f.write(str(task.id))
                    print("Creating .task_id")

                os.chmod(taskid_path, 0o600)
            except Exception as e:
                print(e)
