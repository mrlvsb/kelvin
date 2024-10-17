from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from common.models import Class, Subject, User, Semester, Task, AssignedTask
from django.utils import timezone
import datetime
import os

class Command(BaseCommand):
    def handle(self, *args, **opts):
        teacher, existed = User.objects.get_or_create(
            username='teacher',
            email='teacher@email.com'
        )
        if not existed:
            teachers_group = Group.objects.get(name='teachers')
            teachers_group.user_set.add(teacher)
            teacher.set_password("Kelvin123")
        students = list()
        for i in range(10):
            s, existed = User.objects.get_or_create(
                username=f'student{i + 1}',
                email=f'student{i + 1}@email.com'
            )
            if not existed:
                s.set_password("Kelvin123")
            students.append(s)
        now = datetime.datetime.now(tz=timezone.utc)
        if 1 < now.month < 7:
            semester, _ = Semester.objects.get_or_create(
                begin=f'{now.year}-02-01',
                end=f'{now.year}-07-31',
                year=f'{now.year}',
                winter=False,
                active=True
            )
        else:
            semester, _ = Semester.objects.get_or_create(
                begin=f'{now.year}-10-01',
                end=f'{now.year + 1}-01-31',
                year=f'{now.year}',
                winter=True,
                active=True
            )
        pja, _ = Subject.objects.get_or_create(
            name='Programování v jazyce Ada',
            abbr='PjA'
        )
        upr, _ = Subject.objects.get_or_create(
            name='Úvod do programování',
            abbr='UPR'
        )
        pja_clazz1, _ = Class.objects.get_or_create(
            code='C/01',
            teacher=teacher,
            semester=semester,
            subject=pja,
            day="PO",
            time="15:00"
        )
        pja_clazz2, _ = Class.objects.get_or_create(
            code='C/02',
            teacher=teacher,
            semester=semester,
            subject=pja,
            day="UT",
            time="15:00"
        )
        upr_clazz1, _ = Class.objects.get_or_create(
            code='C/01',
            teacher=teacher,
            semester=semester,
            subject=upr,
            day="ST",
            time="07:15"
        )
        upr_clazz2, _ = Class.objects.get_or_create(
            code='C/02',
            teacher=teacher,
            semester=semester,
            subject=upr,
            day="ST",
            time="08:45"
        )
        for i in range(5):
            pja_clazz1.students.add(students[i])
            pja_clazz2.students.add(students[i + 5])
            upr_clazz1.students.add(students[i])
            upr_clazz2.students.add(students[i + 5])
        task1, _ = Task.objects.get_or_create(
            name="FizzBuzz",
            code='/'.join([upr.abbr, str(semester), teacher.username, upr_clazz1.timeslot, 'fizzbuzz']),
            subject=upr,
            announce=True,
            plagiarism_key=None
        )
        task2, _ = Task.objects.get_or_create(
            name="Cosine similarity",
            code='/'.join([upr.abbr, str(semester), teacher.username, upr_clazz2.timeslot, 'cosine_similarity']),
            subject=upr,
            announce=True,
            plagiarism_key=None
        )
        for task in [
            (task1, [(os.path.join(task1.dir(), ".taskid"), str(task1.pk)),
                     (os.path.join(task1.dir(), "config.yml"), "pipeline:\n  - type: gcc"),
                     (os.path.join(task1.dir(), "readme.md"),
                      "# FizzBuzz\n\nNaimplementujte funkci [FizzBuzz](https://en.wikipedia.org/wiki/Fizz_buzz) a na vhodných datech ukažte její funkčnost.\n\nV této úloze lze získat bonusový bod, zvládnete FizzBuzz naimplementovat bez použití podmínek?")]),
            (
                task2, [(os.path.join(task2.dir(), ".taskid"), str(task2.pk)),
                        (os.path.join(task2.dir(), "config.yml"), "pipeline:\n  - type: gcc"),
                        (os.path.join(task2.dir(), "readme.md"),
                         "# Cosine similarity\n\nNaimplementujte funkci pro počítání [Cosine similarity](https://en.wikipedia.org/wiki/Cosine_similarity) a na vhodných datech ukažte její funkčnost.")])]:
            os.makedirs(task[0].dir(), exist_ok=True)
            for pths in task[1]:
                if not os.path.exists(pths[0]):
                    with open(pths[0], "w") as f:
                        f.write(pths[1])
            AssignedTask.objects.update_or_create(
                task_id=task1.pk,
                clazz_id=upr_clazz1.pk,
                defaults={
                    "assigned": now,
                    "deadline": now+datetime.timedelta(days=7),
                    "max_points": 3,
                },
            )
            AssignedTask.objects.update_or_create(
                task_id=task2.pk,
                clazz_id=upr_clazz2.pk,
                defaults={
                    "assigned": now,
                    "deadline": now+datetime.timedelta(days=14),
                    "max_points": 5,
                },
            )

