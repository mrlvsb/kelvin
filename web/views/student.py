import json
import os
import re
import tarfile
import tempfile
import io
import zipfile

import django_rq
import mimetypes
import rq
import subprocess
import magic
from django.core.files.uploadedfile import UploadedFile

from django.utils import timezone as datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, Http404
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.utils import timezone as tz
from django.urls import reverse

from ..task_utils import highlight_code_json

from common.models import Submit, Class, AssignedTask, Task, Comment, assignedtask_results
from common.evaluate import evaluate_job
from api.models import UserToken
from kelvin.settings import BASE_DIR, MAX_INLINE_CONTENT_BYTES
from ..forms import UploadSolutionForm
from evaluator.testsets import TestSet
from common.evaluate import get_meta
from evaluator.results import EvaluationResult
from common.utils import is_teacher

from notifications.signals import notify
from notifications.models import Notification


@login_required()
def student_index(request):
    result = []

    classess = Class.objects.current_semester().filter(students__pk=request.user.id)

    for clazz in classess:
        tasks = []
        for assignment in AssignedTask.objects.filter(clazz_id=clazz.id).order_by('-id'):
            if not assignment.task.announce and assignment.assigned > datetime.now():
                continue

            data = {
                'id': assignment.id,
                'name': assignment.task.name,
                'deadline': assignment.deadline,
                'assigned': assignment.assigned,
                'assigned_show_remaining': assignment.assigned > datetime.now(),
                'assignment': assignment,
            }

            for student in assignedtask_results(assignment, student__id=request.user.id):
                if student['student'].username == request.user.username:
                    data = {**data, **student}
            tasks.append(data)

        result.append({
            'class': clazz,
            'tasks': tasks,
        })

    return render(request, 'web/index.html', {
        'classess': result,
#        'token': UserToken.objects.get(user__id=request.user.id).token,
    })


def get(submit):
    results = []
    try:
        path = re.sub(r'^submits/', 'submit_results/', str(submit.dir()))
        path = path.rstrip('.c')
        results = EvaluationResult(path)
    except json.JSONDecodeError as e:
        # TODO: show error
        pass

    data = {
        "submit": submit,
        "results": results,
    }
    return data


def store_uploaded_file(submit: Submit, name: str, file):
    path = submit.source_path(name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if isinstance(file, UploadedFile):
        with open(path, "wb") as storage_file:
            for chunk in file.chunks():
                storage_file.write(chunk)
    elif isinstance(file, zipfile.ZipFile):
        file.extract(name, path=submit.dir())
    else:
        raise Exception(f"Invalid file type {type(file)}")


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
    testset = create_taskset(assignment.task, student_username if student_username else request.user.username)
    if (assignment.assigned > datetime.now() or not assignment.clazz.students.filter(username=request.user.username)) and not is_teacher(request.user):
        if assignment.task.announce:
            return render(request, 'web/task_detail.html', {
                'task': assignment.task,
                'assigned': assignment.assigned,
                'deadline': assignment.deadline,
                'text':  testset.load_readme().announce,
                'upload': False,
            })
        raise Http404()


    data = {
        # TODO: task and deadline can be combined into assignment ad deal with it in template
        'task': assignment.task,
        'deadline': assignment.deadline,
        'submits': submits,
        'text':  testset.load_readme(),
        'inputs': testset,
        'max_inline_content_bytes': MAX_INLINE_CONTENT_BYTES,
        'upload': not is_teacher(request.user),
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

        submit_nums = sorted(submits.values_list('submit_num', flat=True))
        current_idx = submit_nums.index(current_submit.submit_num)
        if current_idx - 1 >= 0:
            data['prev_submit'] = submit_nums[current_idx - 1]
        if current_idx + 1 < len(submit_nums):
            data['next_submit'] = submit_nums[current_idx + 1]

        data['total_submits'] = submits.count()
        data['late_submit'] = assignment.deadline and submits.order_by('id').reverse()[0].created_at > assignment.deadline
        data['diff_versions'] = [(s.submit_num, s.created_at) for s in submits.order_by('id')]

        if request.GET.get('clear_notifications'):
            for notification in request.user.notifications.unread().filter(target_object_id=current_submit.id):
                notification.mark_as_read()
            return redirect(request.path_info)

        try:
            job = django_rq.jobs.get_job_class().fetch(current_submit.jobid, connection=django_rq.queues.get_connection())
            status = job.get_status()
            if status == 'queued':
                status += f' {job.get_position() + 1}'
            elif status == 'started':
                if 'actions' in job.meta:
                    percent = job.meta['current_action'] * 100 // job.meta['actions']
                    status = f'evaluating {percent}%'
            data['job_status'] = status
        except rq.exceptions.NoSuchJobError:
            pass

    if request.method == 'POST':
        form = UploadSolutionForm(request.POST, request.FILES)
        if form.is_valid():
            s = Submit()
            s.student = request.user
            s.assignment = assignment
            s.submit_num = Submit.objects.filter(assignment__id=s.assignment.id,
                                                 student__id=request.user.id).count() + 1
            s.save()

            for uploaded_file in request.FILES.getlist('solution'):
                name = uploaded_file.name
                extension = os.path.splitext(name)[1]
                if extension == ".zip":
                    with zipfile.ZipFile(uploaded_file, "r") as archive:
                        for file in archive.filelist:
                            if not file.is_dir():
                                store_uploaded_file(s, file.filename, archive)
                else:
                    store_uploaded_file(s, uploaded_file.name, uploaded_file)

            s.jobid = django_rq.enqueue(evaluate_job, s).id
            s.save()
            return redirect(reverse('task_detail', args=[s.student.username, s.assignment.id, s.submit_num]) + '#result')
    else:
        form = UploadSolutionForm()
    data['upload_form'] = form
    return render(request, 'web/task_detail.html', data)

def comment_recipients(submit, current_author):
    recipients = [
        submit.assignment.clazz.teacher,
        submit.student
    ]

    # add all participants
    for comment in Comment.objects.filter(submit_id=submit.id):
        if comment.author not in recipients:
            recipients.append(comment.author)

    recipients.remove(current_author)
    return recipients

@login_required
def submit_source(request, submit_id, path):
    submit = get_object_or_404(Submit, id=submit_id)
    if not is_teacher(request.user) and request.user.username != submit.student.username:
        raise PermissionDenied()

    for s in submit.all_sources():
        if s.virt == path:
            with open(s.phys, 'rb') as f:
                res = HttpResponse(f)
                mime = mimetypes.MimeTypes().guess_type(s.phys)[0]
                if mime:
                    res['Content-type'] = mime
                res['Accept-Ranges'] = 'bytes'
                return res
    raise Http404()

@login_required
def submit_diff(request, student_username, assignment_id, submit_a, submit_b):
    submit = get_object_or_404(Submit,
            assignment_id=assignment_id,
            student__username=student_username,
            submit_num=submit_a
    )

    if not is_teacher(request.user) and request.user.username != submit.student.username:
        raise PermissionDenied()

    with tempfile.TemporaryFile('r') as diff:
        cmd = [
            "diff", "-ruiw",
            str(submit_a), str(submit_b)
        ]
        subprocess.Popen(cmd, cwd=os.path.dirname(submit.dir()), stdout=diff).wait()
        diff.seek(0)

        out = diff.read()
        out = re.sub(r'^(---|\+\+\+) [0-9]+/', '\\1 ', out, flags=re.M)
        out = "\n".join([line for line in out.split("\n") if not line.startswith('Binary file')])
        resp = HttpResponse(out)
        resp['Content-Type'] = 'text/x-diff'
        return resp

@login_required
def submit_comments(request, assignment_id, login, submit_num):
    submit = get_object_or_404(Submit,
            assignment_id=assignment_id,
            student__username=login,
            submit_num=submit_num
    )

    if not is_teacher(request.user) and request.user.username != submit.student.username:
        raise PermissionDenied()

    def dump_comment(comment):
        return {
            'id': comment.id,
            'author': comment.author.get_full_name(),
            'text': comment.text,
            'can_edit': comment.author == request.user,
        }


    if request.method == 'POST':
        data = json.loads(request.body)
        comment = Comment()
        comment.submit = submit
        comment.author = request.user
        comment.text = data['text']
        comment.source = data['source']
        comment.line = data['line']
        comment.save()

        notify.send(sender=request.user, recipient=comment_recipients(submit, request.user), verb='added new', action_object=comment, target=submit)
        return HttpResponse(json.dumps(dump_comment(comment)))
    elif request.method == 'PATCH':
        data = json.loads(request.body)
        comment = get_object_or_404(Comment, id=data['id'])

        if comment.author != request.user:
            raise PermissionDenied()

        if not data['text']:
            notifications = Notification.objects.all()
            for n in notifications:
                if n.action_object == comment:
                    n.delete()
            comment.delete()

            return HttpResponse()
        else:
            comment.text = data['text']
            comment.save()

            notify.send(sender=request.user, recipient=comment_recipients(submit, request.user), verb='updated', action_object=comment, target=submit)
            return HttpResponse(json.dumps(dump_comment(comment)))

    result = {}
    for source in submit.all_sources():
        mime = magic.Magic(mime=True).from_file(source.phys)
        if mime and mime.startswith('image/'):
            result[source.virt] = {
                'type': 'img',
                'path': source.virt,
                'src': reverse('submit_source', args=[submit.id, source.virt]),
            }
        elif mime and mime.startswith("video/"):
            name = ('.'.join(source.virt.split('.')[:-1]))
            if name not in result:
                result[name] = {
                    'type': 'video',
                    'path': name,
                    'sources': [],
                }
            result[name]['sources'].append(reverse('submit_source', args=[submit.id, source.virt]))
        else:
            lines = []
            content, formatted_lines = highlight_code_json(source.phys)
            for line in formatted_lines:
                lines.append({'content': line, 'comments': []})
            result[source.virt] = {
                'type': 'source',
                'path': source.virt,
                'lines': lines,
                'content': content
            }

    # add comments from pipeline
    resultset = get(submit)
    for pipe in resultset['results']:
        for source, comments in pipe.comments.items():
            for comment in comments:
                try:
                    line = min(len(result[source]['lines']), comment['line']) - 1
                    if not any(filter(lambda c: c['text'] == comment['text'], result[source]['lines'][line]['comments'])):
                        result[source]['lines'][line]['comments'].append({
                            'id': -1,
                            'author': 'Kelvin',
                            'text': comment['text'],
                            'can_edit': False,
                        })
                except KeyError:
                    pass

    for comment in Comment.objects.filter(submit_id=submit.id).order_by('id'):
        try:
            if comment.source not in result or comment.line > len(result[comment.source]['lines']):
                continue

            result[comment.source]['lines'][comment.line - 1]['comments'].append(dump_comment(comment))
        except KeyError:
            pass

    priorities = {
        'video': 0,
        'img': 1,
        'source': 2,
    }
    return HttpResponse(json.dumps(sorted(result.values(), key=lambda f: (priorities[f['type']], f['path']))))

def file_response(file, filename, mimetype):
    response = HttpResponse(file, mimetype)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def raw_test_content(request, task_name, test_name, file):
    task = get_object_or_404(Task, code=task_name)

    tests = create_taskset(task, request.user)

    for test in tests:
        if test.name == test_name:
            if file in test.files:
                return file_response(test.files[file].open('rb'), f"{test_name}.{file}", "text/plain")
    raise Http404()


def create_taskset(task, user):
    task_dir = os.path.join(BASE_DIR, "tasks", task.code)
    return TestSet(task_dir, get_meta(user))

def check_is_task_accessible(request, task):
    if not is_teacher(request.user):
        assigned_tasks = AssignedTask.objects.filter(task_id=task.id, clazz__students__id=request.user.id, assigned__lte=datetime.now())
        if not assigned_tasks:
            raise PermissionDenied()

@login_required
def tar_test_data(request, task_name):
    task = get_object_or_404(Task, code=task_name)
    check_is_task_accessible(request, task)

    tests = create_taskset(task, request.user.username)

    with io.BytesIO() as f:
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
def task_asset(request, task_name, path):
    task = get_object_or_404(Task, code=task_name)
    try:
        check_is_task_accessible(request, task)
    except PermissionDenied:
        if not path.split('/')[-1].startswith('announce.'):
            raise PermissionDenied()

    if '..' in path or path in ['config.yml', 'script.py']:
        raise PermissionDenied()

    system_path = os.path.join("tasks", task_name, path)
    try:
        with open(system_path, 'rb') as f:
            resp = HttpResponse(f)
            mime = mimetypes.MimeTypes().guess_type(system_path)
            if mime:
                resp['Content-Type'] = f"{mime[0]};charset=utf-8"
            return resp
    except FileNotFoundError as e:
        archive_ext = '.tar.gz'
        if system_path.endswith(archive_ext):
            directory = system_path[:-len(archive_ext)]
            if os.path.isdir(directory):
                with io.BytesIO() as f:
                    with tarfile.open(fileobj=f, mode="w:gz") as tar:
                        tar.add(directory, recursive=True, arcname='')
                    f.seek(0)
                    return file_response(f, os.path.basename(system_path), "application/tar")
        raise Http404()

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
                            return file_response(test.files[file][result_type].open('rb'), f"{test_name}.{result_type}", 'text/plain')
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

    with io.BytesIO() as f:
        with tarfile.open(fileobj=f, mode="w:gz") as tar:
            for source in submit.all_sources():
                info = tarfile.TarInfo(source.virt)
                info.size = os.path.getsize(source.phys)
                with open(source.phys, "rb") as fr:
                    tar.addfile(info, fileobj=fr)

        f.seek(0)
        return file_response(f, f"{login}_{submit_num}.tar.gz", "application/tar")


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

