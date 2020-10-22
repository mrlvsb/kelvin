import os

from django.utils import timezone

from django.db import models
from django.conf import settings
from django.urls import reverse
from django.contrib.auth.models import User

def current_semester_conds(prefix=''):
    return {
        f'{prefix}semester__begin__lte': timezone.now(),
        f'{prefix}semester__end__gte': timezone.now()
    }

def current_semester():
    return Semester.objects.filter(
            begin__lte=timezone.now(),
            end__gte=timezone.now()
        ).first()


class ClassManager(models.Manager):
    def current_semester(self):
        return self.filter(**current_semester_conds())

class Semester(models.Model):
    begin = models.DateField()
    end = models.DateField()
    year = models.IntegerField()
    winter = models.BooleanField()

    def __str__(self):
        return f"{self.year}{'W' if self.winter else 'S'}"

class Subject(models.Model):
    name = models.CharField(max_length=60)
    abbr = models.CharField(max_length=10)

    def __str__(self):
        return self.name

class Task(models.Model):
    name = models.CharField(max_length=60)
    code = models.CharField(max_length=60, verbose_name='Directory', unique=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    announce = models.BooleanField(default=False)

    def path_to_code(path):
        path = os.path.realpath(os.path.abspath(path))
        return os.path.relpath(path, os.path.abspath("./tasks"))

    def dir(self):
        return os.path.join("tasks", self.code)

    def sanitized_name(self):
        return self.name.replace('/', '_').replace(' ', '_')

    def code_name(self):
        return self.code.split('/')[-1]

    def __str__(self):
        return self.name

    def readme_path(self):
        readmes = [f for f in os.listdir(self.dir()) if f.lower() == "readme.md"]
        if readmes:
            return os.path.join(self.dir(), readmes[0])
        return None


    def markdown(self):
        try:
            readme = self.readme_path()
            if readme:
                with open(readme) as f:
                    return f.read()
        except FileNotFoundError:
            return ""

class Class(models.Model):
    code = models.CharField(max_length=20)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True)
    students = models.ManyToManyField(settings.AUTH_USER_MODEL, 'students')
    tasks = models.ManyToManyField(Task, through='AssignedTask')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    day = models.CharField(max_length=5)
    time = models.TimeField()

    objects = ClassManager()

    def __str__(self):
        return f"{self.subject.abbr} {self.code} {self.day} {self.time:%H:%M} {self.teacher.last_name if self.teacher else ''}"

    @property
    def timeslot(self):
        return f"{self.day}{self.time.hour:02}{self.time.minute:02}"

    @property
    def week_offset(self):
        def fix(s):
            s = s.replace('ú', 'u')
            s = s.replace('č', 'c')
            s = s.replace('á', 'a')
            return s

        try:
            days = ['po', 'ut', 'st', 'ct', 'pa', 'so', 'ne']
            self.day = days.index(fix(self.day.lower()))
            return self.day * 60 * 60 * 24 + self.time.hour * 60 * 60 + self.time.minute * 60
        except ValueError as e:
            return 0

    def summary(self):
        path = os.path.join(
            "tasks",
            self.subject.abbr,
            str(self.semester),
            self.teacher.username,
            self.timeslot
        )

        while path:
            try:
                with open(os.path.join(path, "summary.md")) as f:
                    return f.read()
            except FileNotFoundError:
                pass
            path = path[:-1]

        return ""


    class Meta:
            verbose_name_plural = "classes"

class AssignedTask(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    clazz = models.ForeignKey(Class, on_delete=models.CASCADE)
    assigned = models.DateTimeField()
    deadline = models.DateTimeField(null=True, blank=True)
    max_points = models.IntegerField(null=True, blank=True)
    moss_url = models.URLField(null=True, blank=True, editable=False)

    def is_visible(self):
        return timezone.now() >= self.assigned

    def __str__(self):
        return f"{self.task.name} {self.clazz}"

class SourcePath:
    def __init__(self, virt, phys):
        self.virt = virt
        self.phys = phys

def submit_assignment_path(assignment):
    return [
        f"{assignment.clazz.semester.year}-{'W' if assignment.clazz.semester.winter else 'S'}",
        assignment.clazz.subject.abbr,
        assignment.clazz.code.replace('/', '')
    ]

class Submit(models.Model):
    assignment = models.ForeignKey(AssignedTask, on_delete=models.CASCADE)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    submit_num = models.IntegerField()
    result = models.TextField(default='')
    points = models.IntegerField(null=True)
    max_points = models.IntegerField(null=True)
    assigned_points = models.FloatField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    jobid = models.CharField(max_length=20, null=True)

    def path_parts(self):
        return [
            *submit_assignment_path(self.assignment),
            self.assignment.task.code,
            f"{self.student.username}",
            f"{self.submit_num}"
        ]

    def dir(self):
        return "/".join([
            "submits",
            *self.path_parts(),
        ])

    def source_path(self, name):
        return os.path.join(self.dir(), name)

    def all_sources(self):
        sources = []
        offset = len(self.dir()) + 1
        for root, dirs, files in os.walk(self.dir()):
            for f in files:
                path = os.path.join(root, f)
                sources.append(SourcePath(path[offset:], path))

        return sources

    def __str__(self):
        return f"#{self.id} {self.student.username} {self.assignment.task.name} {self.submit_num}"

    def notification_str(self):
        return f"{self.assignment.task.name} #{self.submit_num}"

    def notification_url(self):
        return reverse('task_detail', kwargs={
            'student_username': self.student.username,
            'assignment_id': self.assignment.id,
            'submit_num': self.submit_num
        }) + '?clear_notifications=1#src'

class Comment(models.Model):
    submit = models.ForeignKey(Submit, on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()
    source = models.CharField(max_length=255)
    line = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"comment #{self.id}"

    def notification_str(self):
        return "comment"

    def notification_url(self):
        return reverse('task_detail', kwargs={
            'student_username': self.submit.student.username,
            'assignment_id': self.submit.assignment.id,
            'submit_num': self.submit.submit_num
        }) + '?clear_notifications=1#src'

User.add_to_class('notification_str', lambda self: self.get_full_name())

def assignedtask_results(assignment, **kwargs):
    results = {}
    for student in assignment.clazz.students.all().order_by('username'):
        results[student.username] = {
            'student': student,
            'submits': 0,
            'submits_with_assigned_pts': 0,
        }

    assignment_submits = Submit.objects.filter(assignment_id=assignment.id, **kwargs).select_related('student').order_by('id')
    for submit in assignment_submits:
        student_submit_stats = results[submit.student.username]
        student_submit_stats['submits'] += 1

        if 'first_submit_date' not in student_submit_stats:
            student_submit_stats['first_submit_date'] = submit.created_at
        student_submit_stats['last_submit_date'] = submit.created_at

        if student_submit_stats['submits_with_assigned_pts'] == 0:
            if submit.assigned_points is not None or (assignment.deadline and submit.created_at < assignment.deadline):
                student_submit_stats['points'] = submit.points
                student_submit_stats['max_points'] = submit.max_points
                student_submit_stats['assigned_points'] = submit.assigned_points
                student_submit_stats['accepted_submit_num'] = submit.submit_num
                student_submit_stats['accepted_submit_id'] = submit.id

        if submit.assigned_points is not None:
            student_submit_stats['submits_with_assigned_pts'] += 1
            student_submit_stats['assigned_points'] = submit.assigned_points
            student_submit_stats['accepted_submit_num'] = submit.submit_num
            student_submit_stats['accepted_submit_id'] = submit.id

    return sorted(results.values(), key=lambda s: s['student'].username)
