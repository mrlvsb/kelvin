import json
import os
import glob
from datetime import datetime

from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.db.models import Count

from pygments import highlight
from pygments.lexers import CLexer
from pygments.formatters import HtmlFormatter
import markdown2

from common.models import Submit, Class, Task, AssignedTask
from api.models import UserToken
from kelvin.settings import BASE_DIR


def is_teacher(request):
    return request.user.groups.filter(name='teacher').exists()


@login_required()
def student_index(request):
    result = []

    now = datetime.now()
    classess = Class.objects.current_semester().filter(students__pk=request.user.id)
    
    for clazz in classess:
        tasks = []
        for assignment in AssignedTask.objects.filter(clazz_id=clazz.id).order_by('-id'):
            last_submit = Submit.objects.filter(
                assignment__id=assignment.id,
                student__id=request.user.id,
            ).last()

            data = {
                'id': assignment.id,
                'name': assignment.task.name,
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

@login_required()
def index(request):
    if is_teacher(request):
        return teacher_list(request)
    return student_index(request)

def get(submit):
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
def task_detail(request, assignment_id, submit_num=None, student_username=None):
    submits = Submit.objects.filter(
        assignment__pk=assignment_id,
    ).order_by('-id')

    if is_teacher(request):
        submits = submits.filter(student__username=student_username)
    else:
        submits = submits.filter(student__pk=request.user.id)

    assignment = AssignedTask.objects.get(id=assignment_id)

    task_dir = os.path.join(BASE_DIR, "tasks", assignment.task.code)
    text = ""
    try:
        with open(os.path.join(task_dir, "readme.md")) as f:
            text = "\n".join(f.read().splitlines()[1:])
        text = markdown2.markdown(text, extras=["fenced-code-blocks"])
    except FileNotFoundError:
        pass

    data = {
        'task': assignment.task,
        'submits': submits,
        'text': text,
        'inputs': [],
    }

    for test in glob.glob(os.path.join(task_dir, "*.in")):
        name = os.path.basename(test).replace('.in', '')

        stdin = ""
        stdout = ""
        try:
            with open(test) as f:
                stdin = f.read()

            with open(os.path.join(task_dir, f"{name}.out")) as f:
                stdout = f.read()
        except FileNotFoundError:
            pass      

        data['inputs'].append({
            'name': name,
            'stdin': stdin,
            'stdout': stdout,
        })


    current_submit = None
    if submit_num:
        current_submit = submits.get(submit_num=submit_num)
    elif submits:
        current_submit = submits[0]

    if current_submit:
        data = {**data, **get(current_submit)}

    return render(request, 'web/task_detail.html', data)

def teacher_list(request):
    classess = Class.objects.filter(teacher__pk=request.user.id)

    result = []
    for clazz in classess:
        tasks = []
        for task in clazz.tasks.all().order_by('-id'):
            submits = Submit.objects.filter(student__id__in=clazz.students.all(), assignment__task_id=task.id)
            results = []

            for student in clazz.students.all().order_by('username'):
                his_submits = Submit.objects.filter(student__id=student.id, assignment__task_id=task.id)

                record = {
                    'assignment_id': task.id,
                    'student': student,
                    'submits': his_submits.count(),
                    'points': None,
                    'max_points': None,
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
