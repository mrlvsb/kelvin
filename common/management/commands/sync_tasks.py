import os
import re
import datetime

from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth.models import User

from common.models import Task, Subject, AssignedTask, Class, Submit
from web.task_utils import load_readme 

DAYS = ["PO", "UT", "ST", "CT", "PA", "SO", "NE"]


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
            if '/.git' in root:
                continue
            relative_path = os.path.relpath(root, tasks_dir)
            print(relative_path)
            readme = load_readme(relative_path)
            if not readme:
                continue

            try:
                parts = relative_path.split('/')

                abbr = parts[0].upper()
                subject = Subject.objects.get(abbr=abbr)

                task, _ = Task.objects.get_or_create(code=relative_path, defaults={
                    'subject': subject
                })
                task.name = readme.name
                task.announce = True if readme.announce else False
                task.save()

                if re.match("^[0-9]{4}W|S$", parts[1]):
                    year = parts[1][0:4]
                    winter = parts[1][4]

                    teacher = User.objects.filter(username=parts[2])
                    if teacher:
                        teacher = teacher[0]
                        classess = Class.objects.filter(
                                teacher__pk=teacher.id,
                                subject__abbr=abbr,
                                semester__year=year,
                                semester__winter=winter == 'W',
                        )

                        lecture = re.match("^(?P<day>" + '|'.join(DAYS) + ")(?P<hour>[0-9]{2})(?P<minute>[0-9]{2})$", parts[3])
                        if lecture:
                            classess = classess.filter(
                                    day=lecture.group("day"),
                                    time__hour=lecture.group("hour"),
                                    time__minute=lecture.group("minute")
                            )

                        task_dir = parts[-1]
                        match = re.match("^w(?P<week>[0-9]{2})", task_dir)
                        if match:
                            for clazz in classess:
                                start = datetime.datetime.combine(clazz.semester.begin + datetime.timedelta(days=DAYS.index(clazz.day)), clazz.time)
                                start += datetime.timedelta(days=7 * int(match.group('week')))

                                assigned, _ = AssignedTask.objects.update_or_create(task=task, clazz=clazz, defaults={
                                    "assigned": start
                                })
                                print(f"Assigned to {clazz} at {assigned.assigned}")

            except Subject.DoesNotExist:
                print(f"unknown subject: {abbr}")
