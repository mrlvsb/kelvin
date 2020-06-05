from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

from common.utils import is_teacher
from .models import all_exams, ExamException

@login_required()
def index(request):
    try:
        exams = all_exams()

        if not is_teacher(request.user):
            exams = [exam for exam in exams if request.user.username in exam.students]

        return render(request, 'examinator/index.html', {'exams': exams})
    except ExamException as e:
        if is_teacher(request.user):
            return HttpResponse(e)
        return HttpResponse("Error in exam configuration")
