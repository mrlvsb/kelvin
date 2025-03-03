from django.contrib import admin
from quiz.models import Quiz, AssignedQuiz, EnrolledQuiz, TemplateQuiz

admin.site.register(Quiz)
admin.site.register(AssignedQuiz)
admin.site.register(EnrolledQuiz)
admin.site.register(TemplateQuiz)
