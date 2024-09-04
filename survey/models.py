from django.db import models
from django.conf import settings


class Answer(models.Model):
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    survey_name = models.TextField()
    answers = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
