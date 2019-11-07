import json
import os

from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Count

from pygments import highlight
from pygments.lexers import CLexer
from pygments.formatters import HtmlFormatter
import markdown2

from common.models import Submit, Class, Task
from api.models import UserToken
from kelvin.settings import BASE_DIR

@login_required()
def index(request):
    result = []
    classess = Class.objects.filter(students__pk=request.user.id)
    
    for clazz in classess:
        tasks = []
        for task in clazz.tasks.all().order_by('-id'):
            last_submit = Submit.objects.filter(
                assignment__task__id=task.id,
                student__id=request.user.id,
            ).last()

            data = {
                'id': task.id,
                'name': task.name,
                'points': None,
                'max_points': None,
            }

            if last_submit:
                data['points'] = last_submit.points
                data['max_points'] = last_submit.max_points

            tasks.append(data)

        result.append({
            'class': clazz,
            'tasks': tasks,
        })

    return render(request, 'web/index.html', {
        'classess': result,
        'token': UserToken.objects.get(user__id=request.user.id).token,
    })

def get(id):
    submit = Submit.objects.get(id=id)

    source = ""
    with open(submit.source.path) as f:
        source = f.read()

    results = []
    try:
        results = json.loads(submit.result)
    except json.JSONDecodeError as e:
        # TODO: show error
        pass

    data = {
        "submit": submit,
        "results": results,
        "source": highlight(source, CLexer(), HtmlFormatter()),
    }
    return data

@login_required()
def detail(request, id):
    return render(request, 'web/detail.html', get(id))

@login_required()
def task_detail(request, id, submit_id=None):
    task = Task.objects.get(id=id)
    submits = Submit.objects.filter(
        student__pk=request.user.id,
        assignment__task__pk=id,
    ).order_by('-id')


    if not submit_id and submits:
        submit_id = submits[0].id

    assignment = None
    try:
        with open(os.path.join(BASE_DIR, "tasks/{}/readme.md".format(task.code))) as f:
            assignment = "\n".join(f.read().splitlines()[1:])
    except FileNotFoundError:
        pass


    data = {
        'task': task,
        'submits': submits,
        'assignment': markdown2.markdown(assignment, extras=["fenced-code-blocks"]) if assignment else ""
    }

    if submit_id:
        data = {**data, **get(submit_id)}

    return render(request, 'web/task_detail.html', data)

@login_required()
def teacher_list(request):
    classess = Class.objects.filter(teacher__pk=request.user.id)

    result = []
    for clazz in classess:
        tasks = []
        for task in clazz.tasks.all():
            submits = Submit.objects.filter(student__id__in=clazz.students.all(), assignment__task_id=task.id)
            results = []

            for student in clazz.students.all().order_by('username'):
                his_submits = Submit.objects.filter(student__id=student.id, assignment__task_id=task.id)

                record = {
                    'student': student,
                    'submits': his_submits.count(),
                    'points': 0,
                    'max': 0,
                }

                try:
                    last_submit = his_submits.latest('id')
                    record['points'] = last_submit.points
                    record['max_points'] = last_submit.max_points
                except Submit.DoesNotExist:
                    pass

                results.append(record)

            tasks.append({
                'task': task,
                'results': results,
            })      

        result.append({
            'class': clazz,
            'tasks': tasks,
        })

    return render(request, 'web/teacher.html', {
        'classes': result,
    })

def script(request, token):
    data = {
        "token": token,
    }
    return render(request, "web/install.sh", data, "text/x-shellscript")

def uprpy(request):
    with open(os.path.join(BASE_DIR, "scripts/submit.py")) as f:
        return HttpResponse(f.read(), 'text/x-python')
