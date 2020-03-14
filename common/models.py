import os

from datetime import datetime

from django.db import models
from django.conf import settings


class ClassManager(models.Manager):
    def current_semester(self):
        return self.filter(
            semester__begin__lte=datetime.now(),
            semester__end__gte=datetime.now(),
        )

class Semester(models.Model):
    begin = models.DateField()
    end = models.DateField()
    year = models.IntegerField()
    winter = models.BooleanField()

    def __str__(self):
        return f"{self.year}/{'W' if self.winter else 'S'}"

class Subject(models.Model):
    name = models.CharField(max_length=30)
    abbr = models.CharField(max_length=10)

    def __str__(self):
        return self.name

class Task(models.Model):
    name = models.CharField(max_length=60)
    code = models.CharField(max_length=60)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)

    def __str__(self):
        return self.name

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

    class Meta:
            verbose_name_plural = "classes"

class AssignedTask(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    clazz = models.ForeignKey(Class, on_delete=models.CASCADE)
    assigned = models.DateTimeField()
    deadline = models.DateTimeField(null=True, blank=True)
    max_points = models.IntegerField()
    moss_url = models.URLField(null=True, blank=True)

    def __str__(self):
        return f"{self.task.name} {self.clazz}"

class SourcePath:
    def __init__(self, virt, phys):
        self.virt = virt
        self.phys = phys

class Submit(models.Model):
    assignment = models.ForeignKey(AssignedTask, on_delete=models.CASCADE)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    submit_num = models.IntegerField()
    result = models.TextField(default='')
    points = models.IntegerField(null=True)
    max_points = models.IntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def path_parts(self):
        return [
            f"{self.assignment.clazz.semester.year}-{'W' if self.assignment.clazz.semester.winter else 'S'}",
            self.assignment.clazz.subject.abbr,
            self.assignment.clazz.code.replace('/', ''),
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
