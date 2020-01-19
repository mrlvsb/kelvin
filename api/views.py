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
from common.evaluate import evaluate_job

@csrf_exempt
@transaction.atomic
def submit(request, task_code):
    try:
        s = Submit()
        s.source = request.FILES['solution']
        s.student = request.user
        s.assignment = AssignedTask.objects.get(task__code=task_code, clazz__students__id=request.user.id)
        s.submit_num = Submit.objects.filter(assignment__id=s.assignment.id, student__id=request.user.id).count() + 1
        s.save()

        django_rq.enqueue(evaluate_job, s)
    
        return HttpResponse(request.build_absolute_uri(reverse('task_detail', kwargs={'assignment_id': s.assignment.id})))
    except UserToken.DoesNotExist:
        return HttpResponse('Authorization token not found', status=401)
    except AssignedTask.DoesNotExist:
        return HttpResponse('Task does not exist', status=404)
