import json
import os
import re
import io
import glob
import csv
import tarfile
import django_rq
from datetime import datetime
from collections import OrderedDict

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView
from django.db.models import Count
from django.utils import timezone as tz
from django.conf import settings

import tempfile
from django.db.models import Max, F
from shutil import copyfile

import mosspy

from pygments import highlight
from pygments.lexers import CLexer
from pygments.formatters import HtmlFormatter
import markdown2

from common.models import Submit, Class, Task, AssignedTask
from common.evaluate import evaluate_job
from api.models import UserToken
from kelvin.settings import BASE_DIR
from .forms import UploadSolutionForm
from evaluator.testsets import TestSet
from common.evaluate import get_meta
from evaluator.results import EvaluationResult


def is_teacher(user):
    return user.groups.filter(name='teachers').exists()

def highlight_code(path):
    source = ""
    try:
        with open(path) as f:
            source = f.read()
    except UnicodeDecodeError:
        source = "-- source code contains binary data --"
    except FileNotFoundError:
        source = "-- source code not found --"

    return highlight(source, CLexer(), HtmlFormatter(linenos='table', lineanchors='src', anchorlinenos=True))

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
                'deadline': assignment.deadline,
                'tznow': tz.now(),
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
    if is_teacher(request.user):
        return teacher_list(request)
    return student_index(request)

def get(submit):
    results = []
    try:
        path = re.sub(r'^submits/', 'submit_results/', str(submit.source))
        path = path.rstrip('.c')
        results = EvaluationResult(path)
    except json.JSONDecodeError as e:
        # TODO: show error
        pass

    data = {
        "submit": submit,
        "results": results,
        "source": highlight_code(submit.source.path),
    }
    return data

@login_required()
def task_detail(request, assignment_id, submit_num=None, student_username=None):
    submits = Submit.objects.filter(
        assignment__pk=assignment_id,
    ).order_by('-id')

    if is_teacher(request.user):
        submits = submits.filter(student__username=student_username)
    else:
        submits = submits.filter(student__pk=request.user.id)

    assignment = AssignedTask.objects.get(id=assignment_id)

    task_dir = os.path.join(BASE_DIR, "tasks", assignment.task.code)
    text = ""
    try:
        with open(os.path.join(task_dir, "readme.md")) as f:
            text = "\n".join(f.read().splitlines()[1:])
        text = markdown2.markdown(text, extras=["fenced-code-blocks", "tables"])
        text = text.replace('src="figures/', f'src="https://upr.cs.vsb.cz/static/tasks/{assignment.task.code}/figures/')
    except FileNotFoundError:
        pass

    data = {
        # TODO: task and deadline can be combined into assignment ad deal with it in template
        'task': assignment.task,
        'deadline': assignment.deadline,
        'submits': submits,
        'text': text,
        'inputs': [],
        'tznow': tz.now(),
    }

    data['inputs'] = TestSet(task_dir, get_meta(request.user))

    current_submit = None
    if submit_num:
        current_submit = submits.get(submit_num=submit_num)
    elif submits:
        current_submit = submits[0]

    if current_submit:
        data = {**data, **get(current_submit)}

    if request.method == 'POST':
        form = UploadSolutionForm(request.POST, request.FILES)
        if form.is_valid():
            s = Submit()
            s.source = request.FILES['solution']
            s.student = request.user
            s.assignment = assignment
            s.submit_num = Submit.objects.filter(assignment__id=s.assignment.id, student__id=request.user.id).count() + 1
            s.save()
            django_rq.enqueue(evaluate_job, s)
            return redirect(request.path_info + '#result')
    else:
        form = UploadSolutionForm()
    data['upload_form'] = form
    return render(request, 'web/task_detail.html', data)


@user_passes_test(is_teacher)
def teacher_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)

    task_dir = os.path.join(BASE_DIR, "tasks", task.code)
    text = ""
    try:
        with open(os.path.join(task_dir, "readme.md")) as f:
            text = "\n".join(f.read().splitlines()[1:])
        text = markdown2.markdown(text, extras=["fenced-code-blocks", "tables"])
        text = text.replace('src="figures/', f'src="https://upr.cs.vsb.cz/static/tasks/{task.code}/figures/')
    except FileNotFoundError:
        pass

    data = {
        'task': task,
        'text': text,
        'inputs': [],
    }

    data['inputs'] = TestSet(task_dir, get_meta(request.user))

    return render(request, 'web/task_detail.html', data)


def teacher_list(request):
    classess = Class.objects.filter(teacher__pk=request.user.id)

    result = []
    for clazz in classess:
        tasks = []

        for assignment in clazz.assignedtask_set.all().order_by('-id'):
            results = []

            for student in clazz.students.all().order_by('username'):
                his_submits = Submit.objects.filter(student__id=student.id, assignment__id=assignment.id)

                record = {
                    'assignment_id': assignment.id,
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
                'task': assignment.task,
                'assignment': assignment,
                'results': results,
                'tznow': tz.now(),
            })      

        result.append({
            'class': clazz,
            'tasks': tasks,
        })

    return render(request, 'web/teacher.html', {
        'classes': result,
    })

@login_required
def moss_check(request, assignment_id):
    m = mosspy.Moss(settings.MOSS_USERID, "c")

    with tempfile.TemporaryDirectory() as temp_dir:
        processed = set()
        submits = Submit.objects.filter(assignment_id=assignment_id).order_by('-submit_num')
        for submit in submits:
            if submit.student_id not in processed:
                dst = os.path.join(temp_dir, f"{submit.student.username}.c")
                copyfile(submit.source.path, dst)
                m.addFile(dst)
                print(dst)

                processed.add(submit.student_id)

        assignment = AssignedTask.objects.get(id=assignment_id)
        assignment.moss_url = m.send()
        assignment.save()

        return redirect(assignment.moss_url)

@user_passes_test(is_teacher)
def submits(request):
    submits = Submit.objects.all().order_by('-id')[:100]
    return render(request, "web/submits.html", {'submits': submits})


def script(request, token):
    data = {
        "token": token,
    }
    return render(request, "web/install.sh", data, "text/x-shellscript")

def uprpy(request):
    with open(os.path.join(BASE_DIR, "scripts/submit.py")) as f:
        return HttpResponse(f.read(), 'text/x-python')

@login_required
def project(request, project_type):
    if project_type not in ['normal', 'bonus']:
        return HttpResponse(code=404)

    with open(os.path.join(BASE_DIR, "projects", project_type, "assigned", f"{request.user.username}.html")) as f:
        return HttpResponse(f.read(), 'text/html')

def get_last_submits(assignment_id):
    submits = Submit.objects.filter(assignment_id=assignment_id).order_by('-submit_num', 'student_id')

    result = []
    processed = set()
    for submit in submits:
        if submit.student_id not in processed:            
            result.append(submit)
            processed.add(submit.student_id)

    return result

@user_passes_test(is_teacher)
def download_assignment_submits(request, assignment_id):
    with tempfile.TemporaryFile(suffix=".tar.gz") as f:
        with tarfile.open(fileobj=f, mode="w:gz") as tar:
            targets = []
            for submit in get_last_submits(assignment_id):
                tar.add(submit.source.path, f"{submit.student.username}.c")
                targets.append(submit.student.username)
        
            template = f"""
CFLAGS=-lm
CC=-gcc
all: {' '.join(targets)}

clean:
\trm -f {' '.join(targets)}
            """

            makefile = tarfile.TarInfo('Makefile')
            makefile.size = len(template)
            tar.addfile(makefile, fileobj=io.BytesIO(template.encode('utf-8')))

        f.seek(0)
        response = HttpResponse(f.read(), 'application/tar')
        response['Content-Disposition'] = f'attachment; filename="submits.tar.gz"'
        return response
    
@user_passes_test(is_teacher)
def show_assignment_submits(request, assignment_id):
    submits = []
    for submit in get_last_submits(assignment_id):
        submits.append({
            'submit': submit,
            'source': highlight_code(submit.source.path),
        })

    return render(request, 'web/submits_show_source.html', {
        'submits': submits,
    })


def student_scores(assigned_task):
    for student in assigned_task.clazz.students.all():
        last_submit = Submit.objects.filter(student=student, assignment=assigned_task).order_by('-submit_num')
        if len(last_submit) > 0:
            # TODO: Multiply by assigned_task.max_points
            if last_submit[0].max_points == 0:
                success_rate = 0
            else:
                success_rate = last_submit[0].points / last_submit[0].max_points
            yield student.username, success_rate
        else:
            yield student.username, 0.0

@user_passes_test(is_teacher)
def download_csv_per_task(request, assignment_id : int):
    assigned_task = AssignedTask.objects.get(pk=assignment_id)

    csv_str = '\n'.join((f'{l},{s}' for l, s in student_scores(assigned_task)))
    response = HttpResponse(csv_str, 'text/csv')
    csv_filename = f"{assigned_task.task.code}_{assigned_task.clazz.code}_success_rate.csv"
    response['Content-Disposition'] = f'attachment; filename="{csv_filename}"'

    return response

@user_passes_test(is_teacher)
def download_csv_per_class(request, class_id : int):
    clazz = Class.objects.get(pk=class_id)
    result = OrderedDict()

    header = ['LOGIN']
    for assignment in clazz.assignedtask_set.all():
        header.append(assignment.task.name)

        for login, score in student_scores(assignment):
            if login not in result:
                result[login] = {'LOGIN': login}

            result[login][assignment.task.name] = score

    with io.StringIO() as out:
        w = csv.DictWriter(out, fieldnames=header)
        w.writeheader()

        for login, row in result.items():
            w.writerow(row)

        response = HttpResponse(out.getvalue(), 'text/csv')
        response['Content-Disposition'] = f'attachment; filename="{clazz.code}_success_rate.csv"'
        return response
