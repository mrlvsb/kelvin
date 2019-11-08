import json
from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.urls import reverse
from common.models import Submit, AssignedTask
from .models import UserToken
from django.db import transaction
import django_rq
from evaluator.evaluator import evaluate


@django_rq.job
def post(s: Submit):
    result = evaluate(
        "tasks/{}".format(s.assignment.task.code),
        s.source.path,
    )

    s.result = json.dumps(result, indent=4)

    # calculate points
    s.points = 0
    s.max_points = 0
    for i in result:
        for test in i['tests']:
            if test['success']:
                s.points += 1
            s.max_points += 1

    s.save()

@csrf_exempt
@transaction.atomic
def submit(request, task_code):
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return HttpResponse(status=400)

    token = auth_header.split(' ')[-1]
    found_token = UserToken.objects.filter(token=token).first()
    if not found_token:
        return HttpResponse(status=401)
    
    s = Submit()
    s.source = request.FILES['solution']
    s.student = found_token.user
    s.assignment = AssignedTask.objects.get(task__code=task_code, clazz__students__id=found_token.user.id)
    s.submit_num = Submit.objects.filter(assignment__id=s.assignment.id, student__id=found_token.user.id).count() + 1
    s.save()

    django_rq.enqueue(post, s)
   
    return HttpResponse('ok')
        #request.build_absolute_uri(reverse('submit_detail', kwargs={'id': s.id}))
