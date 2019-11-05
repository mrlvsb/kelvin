import json
import os

from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView

from pygments import highlight
from pygments.lexers import CLexer
from pygments.formatters import HtmlFormatter
import markdown2

from kelvin.models import Submit, Class, Task
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
                task__id=task.id,
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

    return render(request, 'index.html', {
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
    return render(request, "detail.html", get(id))

@login_required()
def task_detail(request, id, submit_id=None):
    task = Task.objects.get(id=id)
    submits = Submit.objects.filter(
        student__pk=request.user.id,
        task__pk=id,
    ).order_by('-id')


    if not submit_id and submits:
        submit_id = submits[0].id

    assignment = None
    try:
        with open(os.path.join(BASE_DIR, "tasks/{}/readme.md".format(id))) as f:
            assignment = f.read()
    except FileNotFoundError:
        pass


    data = {
        'task': task,
        'submits': submits,
        'assignment': markdown2.markdown(assignment, extras=["fenced-code-blocks"]) if assignment else ""
    }

    if submit_id:
        data = {**data, **get(submit_id)}

    return render(request, "task_detail.html", data)

@login_required()
def ll(request):
    return HttpResponse("In login.")

def script(request, token):
    data = {
        "token": token,
    }
    return render(request, "install.sh", data, "text/x-shellscript")

def uprpy(request):
    with open(os.path.join(BASE_DIR, "../../scripts/submit.py")) as f:
        return HttpResponse(f.read(), 'text/x-python')
