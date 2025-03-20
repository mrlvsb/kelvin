import os
import errno
from shutil import copytree, rmtree

from django.db import models
from serde.yaml import from_yaml
from common.models import Class, Subject, User
from api.dto import QuizDto

from quiz.settings import QUIZ_PATH


# Model that represents a quiz
class Quiz(models.Model):
    name = models.CharField(max_length=100)
    # path for quiz relative to path defined in settings.py
    src = models.CharField(max_length=255, verbose_name="Directory", unique=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    # Method that writes content to the quiz file.
    def write(self, yaml_content: str):
        with open(self.get_file_path(), "w", encoding="utf-8") as file:
            file.write(yaml_content)

    # Method that reads content from the quiz file.
    def read(self):
        with open(self.get_file_path(), "r", encoding="utf-8") as file:
            return file.read()

    # Method that returns the directory path of the quiz.
    def get_directory_path(self):
        return os.path.join(QUIZ_PATH, self.src)

    # Method that returns the file path of the quiz.
    def get_file_path(self):
        return os.path.join(self.get_directory_path(), "quiz.yml")

    # Method that returns the identifier file path of the quiz.
    def get_identifier_path(self):
        return os.path.join(self.get_directory_path(), ".quiz_id")

    # Method that returns a DTO of the quiz
    def get_dto(self):
        return from_yaml(QuizDto, self.read())

    # Method that tries to set up the new directory for the quiz
    def set_up_directory(self, new_src: str):
        copytree(os.path.join(QUIZ_PATH, self.src), os.path.join(QUIZ_PATH, new_src))

        old_src = self.src

        self.src = new_src

        self.save()

        rmtree(os.path.join(QUIZ_PATH, old_src))

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

    # Method that sums assigned scores of questions and returns the total score of the quiz.
    def score(self):
        score = 0.0
        for key in self.scoring:
            score += float(self.scoring[key]["points"])
        return score

    class Meta:
        verbose_name_plural = "Enrolled quizzes"


