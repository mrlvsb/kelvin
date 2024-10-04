from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from common.models import Class, Subject, User, Semester

class Command(BaseCommand):
    def handle(self, *args, **opts):
        teacher,created = User.objects.get_or_create(
            username='teacher',
            password='teacher007',
            email='teacher@email.com'
        )
        if not created:
            teachers_group = Group.objects.get(name='teachers')
            teachers_group.user_set.add(teacher)
        students = list()
        for i in range(10):
            s,_ = User.objects.get_or_create(
                username=f'student{i+1}',
                password='student007',
                email=f'student{i+1}@email.com'
            )
            students.append(s)
        semester,_ = Semester.objects.get_or_create(
            begin = '2024-10-01',
            end = '2025-01-31',
            year = '2024',
            winter = True,
            active = True
        )
        pja,_ = Subject.objects.get_or_create(
            name='Programovani v jazyce Ada',
            abbr='PjA'
        )
        pjp,_ = Subject.objects.get_or_create(
            name='Programovani v jazyce Pascal',
            abbr='PjP'
        )
        pja_clazz1,_ = Class.objects.get_or_create(
            code='C/01',
            teacher=teacher,
            semester=semester,
            subject=pja,
            day="PO",
            time="15:00"
        )
        pja_clazz2,_ = Class.objects.get_or_create(
            code='C/02',
            teacher=teacher,
            semester=semester,
            subject=pja,
            day="UT",
            time="15:00"
        )
        pjp_clazz1, _ = Class.objects.get_or_create(
            code='C/01',
            teacher=teacher,
            semester=semester,
            subject=pjp,
            day="ST",
            time="7:15"
        )
        pjp_clazz2, _ = Class.objects.get_or_create(
            code='C/02',
            teacher=teacher,
            semester=semester,
            subject=pjp,
            day="ST",
            time="8:45"
        )
        for i in range(5):
            pja_clazz1.students.add(students[i])
            pja_clazz2.students.add(students[i+5])
            pjp_clazz1.students.add(students[i])
            pjp_clazz2.students.add(students[i+5])

