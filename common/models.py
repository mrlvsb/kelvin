from django.db import models
from django.conf import settings
from .utils import current_semester


class ClassManager(models.Manager):
    def current_semester(self):
        year, winter = current_semester()

        return self.filter(
            year=year,
            winter=winter
        )


class Task(models.Model):
    name = models.CharField(max_length=60)
    code = models.CharField(max_length=60)

    def __str__(self):
        return self.name

class Class(models.Model):
    code = models.CharField(max_length=20)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True)
    students = models.ManyToManyField(settings.AUTH_USER_MODEL, 'students')
    tasks = models.ManyToManyField(Task, through='AssignedTask')
    year = models.IntegerField()
    winter = models.BooleanField()
    day = models.CharField(max_length=5)
    time = models.TimeField()

    objects = ClassManager()

    def __str__(self):
        return f"{self.code} {self.day} {self.time:%H:%M} {self.teacher.last_name if self.teacher else ''}"

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

def submit_path_parts(submit):
    return [
        f"{submit.assignment.clazz.year}-{'W' if submit.assignment.clazz.winter else 'S'}",
        submit.assignment.clazz.code.replace('/', ''),
        submit.assignment.task.code,
    ]

def submit_path(submit, filename):
    return "/".join([
        "submits",
        *submit_path_parts(submit),
        f"{submit.student.username}_{submit.submit_num}.c"
    ])

class Submit(models.Model):
    assignment = models.ForeignKey(AssignedTask, on_delete=models.CASCADE)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    submit_num = models.IntegerField()
    source = models.FileField(upload_to=submit_path)
    result = models.TextField(default='')
    points = models.IntegerField(null=True)
    max_points = models.IntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.username} {self.assignment.task.name} {self.submit_num}"
