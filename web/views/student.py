import json
import os
import re
import tarfile
import tempfile
import io
import django_rq
from django.utils import timezone as datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, Http404
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.utils import timezone as tz

from ..task_utils import highlight_code, render_markdown

from common.models import Submit, Class, AssignedTask, Task
from common.evaluate import evaluate_job
from api.models import UserToken
from kelvin.settings import BASE_DIR, MAX_INLINE_CONTENT_BYTES
from ..forms import UploadSolutionForm
from evaluator.testsets import TestSet
from common.evaluate import get_meta
from evaluator.results import EvaluationResult
from common.utils import is_teacher


@login_required()
def student_index(request):
    result = []

    now = datetime.now()
    classess = Class.objects.current_semester().filter(students__pk=request.user.id)

    for clazz in classess:
        tasks = []
        for assignment in AssignedTask.objects.filter(clazz_id=clazz.id, assigned__lte=datetime.now()).order_by('-id'):
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

    assignment = get_object_or_404(AssignedTask, id=assignment_id)
    if (assignment.assigned > datetime.now() or not assignment.clazz.students.filter(username=request.user.username)) and not is_teacher(request.user):
        raise Http404()

    testset = create_taskset(assignment.task, request.user)

    data = {
        # TODO: task and deadline can be combined into assignment ad deal with it in template
        'task': assignment.task,
        'deadline': assignment.deadline,
        'submits': submits,
        'text': render_markdown(testset.task_path, assignment.task.code),
        'inputs': testset,
        'tznow': tz.now(),
        'max_inline_content_bytes': MAX_INLINE_CONTENT_BYTES,
    }

    current_submit = None
    if submit_num:
        try:
            current_submit = submits.get(submit_num=submit_num)
        except Submit.DoesNotExist:
            raise Http404()
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
            s.submit_num = Submit.objects.filter(assignment__id=s.assignment.id,
                                                 student__id=request.user.id).count() + 1
            s.save()
            django_rq.enqueue(evaluate_job, s)
            return redirect(request.path_info + '#result')
    else:
        form = UploadSolutionForm()
    data['upload_form'] = form
    return render(request, 'web/task_detail.html', data)


def file_response(file, filename, mimetype):
    content = file.read()
    response = HttpResponse(content, mimetype)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def raw_test_content(request, task_name, test_name, file):
    task = get_object_or_404(Task, code=task_name)

    tests = create_taskset(task, request.user)

    for test in tests:
        if test.name == test_name:
            if file in test.files:
                return file_response(test.files[file], f"{test_name}.{file}", "text/plain")
    raise Http404()


def create_taskset(task, user):
    task_dir = os.path.join(BASE_DIR, "tasks", task.code)
    return TestSet(task_dir, get_meta(user))


@login_required
def tar_test_data(request, task_name):
    task = get_object_or_404(Task, code=task_name)
    if not is_teacher(request.user):
        assigned_tasks = AssignedTask.objects.filter(task_id=task.id, clazz__students__id=request.user.id)
        if not assigned_tasks:
            raise PermissionDenied()

    tests = create_taskset(task, request.user)

    f = io.BytesIO()
    with tarfile.open(fileobj=f, mode="w:gz") as tar:
        for test in tests:
            for file_path in test.files:
                test_file = test.files[file_path]
                info = tarfile.TarInfo(os.path.join(test.name, file_path))
                info.size = test_file.size()
                tar.addfile(info, fileobj=test_file.open('rb'))

    f.seek(0)
    return file_response(f, f"{task_name}.tar.gz", "application/tar")


@login_required
def raw_result_content(request, submit_id, test_name, result_type, file):
    submit = get_object_or_404(Submit, pk=submit_id)
    
    if submit.student_id != request.user.id and not is_teacher(request.user):
        raise PermissionDenied()

    for pipe in get(submit)['results']:
        for test in pipe.tests:
            if test.name == test_name:
                if file in test.files:
                    if result_type in test.files[file]:
                        if result_type == "html":
                            return HttpResponse(test.files[file][result_type].read(),
                                                'text/html' if result_type == 'html' else 'text/plain')
                        else:
                            return file_response(test.files[file][result_type], f"{test_name}.{result_type}", 'text/plain')
    raise Http404()


@login_required
def submit_download(request, assignment_id, login, submit_num):
    submit = get_object_or_404(Submit,
            assignment_id=assignment_id,
            student__username=login,
            submit_num=submit_num
    )

    if not is_teacher(request.user) and request.user.username != submit.student.username:
        raise PermissionDenied()

    res = HttpResponse(submit.source, 'text/plain')
    res['Content-Disposition'] = f'attachment; filename="{login}_{submit_num}.c"'
    return res


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
