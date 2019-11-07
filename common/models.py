from django.db import models
from django.conf import settings


class Task(models.Model):
    name = models.CharField(max_length=60)
    code = models.CharField(max_length=60)

    def __str__(self):
        return self.name

class Class(models.Model):
    name = models.CharField(max_length=60)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    students = models.ManyToManyField(settings.AUTH_USER_MODEL, 'students')
    tasks = models.ManyToManyField(Task, through='TaskInClass')

    def __str__(self):
        return self.name

class TaskInClass(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    clazz = models.ForeignKey(Class, on_delete=models.CASCADE)
    assigned = models.DateTimeField()
    deadline = models.DateTimeField()
    max_points = models.IntegerField()

def submit_path(submit, filename):
    return f"submits/{submit.task.id}/{submit.student.username}.c"

class Submit(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    source = models.FileField(upload_to=submit_path)
    result = models.TextField(default='')
    evaluated_points = models.IntegerField(null=True)
    points = models.IntegerField(null=True)
    max_points = models.IntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

