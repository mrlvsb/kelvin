import os

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.http import HttpResponseForbidden


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

@login_required()
def show_upload(request, exam_id, student, filename):
    if not is_teacher(request.user) and student != request.user.username:
        return HttpResponseForbidden()

    if '..' in exam_id or '..' in filename:
        return HttpResponseForbidden()

    with open(os.path.join("exams", exam_id, student, "uploads", filename), "rb") as f:
        resp = HttpResponse(f)
        resp['Content-Type'] = 'application/octet-stream'
        return resp


