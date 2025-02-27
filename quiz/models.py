from django.db import models
from common.models import Class, Subject, User, Semester


# Model that represents a quiz
class Quiz(models.Model):
    name = models.CharField(max_length=100)
    # path for quiz relative to directory defined in settings.py
    src = models.CharField(max_length=255, verbose_name="Directory", unique=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Quizzes"


# Model that represents an assigned quiz
class AssignedQuiz(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE)
    clazz = models.ForeignKey(Class, on_delete=models.CASCADE)
    assigned = models.DateTimeField()
    # duration of quiz in minutes
    duration = models.IntegerField()
    deadline = models.DateTimeField()
    publish_results = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.quiz.name} {self.clazz}"

    class Meta:
        verbose_name_plural = "Assigned quizzes"


# Model that represents a template of enrolled quiz
class TemplateQuiz(models.Model):
    content = models.JSONField(default=dict)
    # computed hash of enrolled quiz template
    hash = models.CharField(max_length=255, unique=True)
    max_points = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Quiz template {self.id}"

    class Meta:
        verbose_name_plural = "Quiz templates"


# Model that represents an enrolled quiz
class EnrolledQuiz(models.Model):
    assigned_quiz = models.ForeignKey(AssignedQuiz, on_delete=models.CASCADE)
    template = models.ForeignKey(TemplateQuiz, on_delete=models.CASCADE)
    student = models.ForeignKey(User, on_delete=models.CASCADE)
    deadline = models.DateTimeField()
    submit = models.JSONField(default=dict)
    scoring = models.JSONField(default=dict)
    scored_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="scored_by", null=True
    )
    submitted = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.assigned_quiz.quiz.name} {self.student} {self.id}"

    class Meta:
        verbose_name_plural = "Enrolled quizzes"
