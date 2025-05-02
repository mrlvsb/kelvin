import os
from shutil import copytree, rmtree

from django.db import models
from serde.yaml import from_yaml
from common.models import Class, Subject, User
from api.dto import QuizDto

from quiz.settings import QUIZ_PATH


class Quiz(models.Model):
    """
    Model that represents a quiz.
    """

    name = models.CharField(max_length=100)
    # path for quiz relative to path defined in settings.py
    src = models.CharField(max_length=255, verbose_name="Directory", unique=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def write(self, yaml_content: str):
        """
        Method that writes content to the quiz file.
        """
        with open(self.get_file_path(), "w", encoding="utf-8") as file:
            file.write(yaml_content)

    def read(self):
        """
        Method that reads content from the quiz file.
        """
        with open(self.get_file_path(), "r", encoding="utf-8") as file:
            return file.read()

    def get_directory_path(self):
        """
        Method that returns the directory path of the quiz.
        """
        return os.path.join(QUIZ_PATH, self.src)

    def get_file_path(self):
        """
        Method that returns the file path of the quiz.
        """
        return os.path.join(self.get_directory_path(), "quiz.yml")

    def get_identifier_path(self):
        """
        Method that returns the identifier file path of the quiz.
        """
        return os.path.join(self.get_directory_path(), ".quiz_id")

    def get_dto(self):
        """
        Method that returns a DTO of the quiz.
        """
        return from_yaml(QuizDto, self.read())

    def set_up_directory(self, new_src: str):
        """
        Method that tries to set up the new directory for the quiz.
        """
        copytree(os.path.join(QUIZ_PATH, self.src), os.path.join(QUIZ_PATH, new_src))

        old_src = self.src

        self.src = new_src

        self.save()

        rmtree(os.path.join(QUIZ_PATH, old_src))

    class Meta:
        verbose_name_plural = "Quizzes"


class AssignedQuiz(models.Model):
    """
    Model that represents an assigned quiz.
    """

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

    def max_points(self):
        """
        Method that returns the maximum points of the assigned quiz.
        """
        quiz_dto = self.quiz.get_dto()

        return sum(map(lambda q: q.points, quiz_dto.questions))

    class Meta:
        verbose_name_plural = "Assigned quizzes"


class TemplateQuiz(models.Model):
    """
    Model that represents a template of enrolled quiz.
    """

    content = models.JSONField(default=dict)
    # computed hash of enrolled quiz template
    hash = models.CharField(max_length=255, unique=True)
    max_points = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Quiz template {self.id}"

    class Meta:
        verbose_name_plural = "Quiz templates"


class EnrolledQuiz(models.Model):
    """
    Model that represents an enrolled quiz.
    """

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

    def score(self):
        """
        Method that sums assigned scores of questions and returns the total score of the quiz.
        """
        score = 0.0
        for key in self.scoring:
            score += float(self.scoring[key]["points"])
        return score

    class Meta:
        verbose_name_plural = "Enrolled quizzes"
