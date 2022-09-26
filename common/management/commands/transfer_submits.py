import os
import re
import shutil

from django.core.management.base import BaseCommand

from common.models import AssignedTask, Class, Submit

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('assignment_id')
        parser.add_argument('--really', action='store_true')

    def handle(self, *args, **opts):
        for submit in Submit.objects.filter(assignment_id=opts['assignment_id']):
            c = Class.objects.get(
                students__in=[submit.student_id],
                code__startswith='C/',
                subject_id=submit.assignment.clazz.subject_id,
                semester_id=submit.assignment.clazz.semester_id,
            )

            new_assigned_task = AssignedTask.objects.get(
                task_id=submit.assignment.task_id,
                clazz_id=c.id,
            )

            submits = len(Submit.objects.filter(
                assignment_id=new_assigned_task.id,
                student_id=submit.student_id,
            ))

            prev_dir = submit.dir()
            submit.assignment_id = new_assigned_task.id
            submit.submit_id = submits + 1

            if opts['really']:
                shutil.move(prev_dir, submit.dir())
                submit.save()

            print(submit, c, new_assigned_task, submits)
       