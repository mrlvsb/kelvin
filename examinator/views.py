from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from common.utils import is_teacher
from .models import all_exams

@login_required()
def index(request):
    exams = all_exams()

    if not is_teacher(request.user):
        exams = [exam for exam in exams if request.user.username in exam.students]

    return render(request, 'examinator/index.html', {'exams': exams})
