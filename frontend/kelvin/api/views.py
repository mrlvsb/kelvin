from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from kelvin.models import Submit, Task
from django.contrib.auth.models import User
from django.urls import reverse
from .models import UserToken

@csrf_exempt
def submit(request, task_num):
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
    s.task = Task.objects.get(id=task_num)
    s.save()
   
    return HttpResponse('ok')
        #request.build_absolute_uri(reverse('submit_detail', kwargs={'id': s.id}))
