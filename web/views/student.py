import json
import os
import re
import tarfile
import tempfile
import io
import zipfile
import shutil
import hashlib

import django_rq
import rq
import subprocess
import magic
import logging

from django.core.files.uploadedfile import UploadedFile
from django.utils import timezone as datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, Http404, HttpResponseBadRequest, JsonResponse, HttpResponseForbidden
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.contrib.auth.decorators import login_required
from django.utils import timezone as tz
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType

from common.models import Submit, Class, AssignedTask, Task, Comment, assignedtask_results
from common.evaluate import evaluate_job
from web.task_utils import load_readme
from api.models import UserToken
from kelvin.settings import BASE_DIR, MAX_INLINE_CONTENT_BYTES
from ..forms import UploadSolutionForm
from evaluator.testsets import TestSet
from common.evaluate import get_meta
from evaluator.results import EvaluationResult
from common.utils import is_teacher

from notifications.signals import notify
from notifications.models import Notification

mimedetector = magic.Magic(mime=True)


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
        results = EvaluationResult(submit.pipeline_path())
    except json.JSONDecodeError as e:
        # TODO: show error
        pass

    data = {
        "submit": submit,
        "results": results,
    }
    return data


SUBMIT_DROPPED_MIMES = [
    'application/x-object',
    'application/x-pie-executable',
    'application/x-sharedlib'
]
def store_uploaded_file(submit: Submit, path: str, file):
    if path[0] == '/' or '..' in path:
        raise SuspiciousOperation()

    target_path = submit.source_path(path)
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    if isinstance(file, UploadedFile):
        with open(target_path, "wb") as storage_file:
            for chunk in file.chunks():
                storage_file.write(chunk)
    elif isinstance(file, zipfile.ZipFile):
        file.extract(path, path=submit.dir())
    else:
        raise Exception(f"Invalid file type {type(file)}")

    mime = mimedetector.from_file(target_path)
    if mime in SUBMIT_DROPPED_MIMES:
        os.unlink(target_path)


def get_submit_job_status(jobid):
    try:
        job = django_rq.jobs.get_job_class().fetch(jobid, connection=django_rq.queues.get_connection())
        status = job.get_status()
        if status == 'queued':
            return False, f'in queue: {job.get_position() + 1}'
        elif status == 'started':
            if 'actions' in job.meta and job.meta['actions'] > 0:
                percent = job.meta['current_action'] * 100 // job.meta['actions']
                return False, f'evaluating {percent}%'
        elif status == 'finished':
            return True, 'finished'
        return False, status
    except rq.exceptions.NoSuchJobError:
        return True, ''
    except AttributeError:
        return False, ''
    return True, ''

@login_required()
def pipeline_status(request, submit_id):
    submit = get_object_or_404(Submit, id=submit_id)

    if not is_teacher(request.user) and request.user != submit.student:
        return HttpResponseForbidden()

    finished, status = get_submit_job_status(submit.jobid)
    return JsonResponse({
        'status': status,
        'finished': finished,
    })

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
        'upload': not is_teacher(request.user) or request.user.username == student_username,
        'has_pipeline': bool(testset.pipeline),
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
        data['comment_count'] = current_submit.comment_set.count()

        submit_nums = sorted(submits.values_list('submit_num', flat=True))
        current_idx = submit_nums.index(current_submit.submit_num)
        if current_idx - 1 >= 0:
            data['prev_submit'] = submit_nums[current_idx - 1]
        if current_idx + 1 < len(submit_nums):
            data['next_submit'] = submit_nums[current_idx + 1]

        data['total_submits'] = submits.count()
        data['late_submit'] = assignment.deadline and submits.order_by('id').reverse()[0].created_at > assignment.deadline
        data['diff_versions'] = [(s.submit_num, s.created_at) for s in submits.order_by('id')]
        data['job_status'] = not get_submit_job_status(current_submit.jobid)[0]

    if request.method == 'POST':
        form = UploadSolutionForm(request.POST, request.FILES)
        if form.is_valid():
            s = Submit()
            s.student = request.user
            s.assignment = assignment
            s.submit_num = Submit.objects.filter(assignment__id=s.assignment.id,
                                                 student__id=request.user.id).count() + 1
            s.save()

            solutions = request.FILES.getlist('solution')
            tmp = request.POST.get('paths', None)
            paths = []
            if tmp:
                paths = [f.rstrip('\r') for f in tmp.split('\n')]
            else:
                paths = [f.name for f in solutions]
            for path, uploaded_file in zip(paths, solutions):
                extension = os.path.splitext(path)[1]
                if extension.lower() == ".zip":
                    with zipfile.ZipFile(uploaded_file, "r") as archive:
                        for file in archive.filelist:
                            if not file.is_dir():
                                store_uploaded_file(s, file.filename, archive)
                else:
                    store_uploaded_file(s, path, uploaded_file)

            s.jobid = django_rq.enqueue(evaluate_job, s).id
            s.save()

            # delete previous notifications
            Notification.objects.filter(
                action_object_object_id__in=submits,
                action_object_content_type=ContentType.objects.get_for_model(Submit),
                verb='submitted',
            ).delete()

            if not is_teacher(request.user):
                notify.send(sender=request.user, recipient=[assignment.clazz.teacher],
                            verb='submitted', action_object=s)

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
            path = s.phys
            mime = mimedetector.from_file(s.phys)
            if request.GET.get('convert', False):
                key = hashlib.sha1(f"{submit_id}{path}".encode('utf-8')).hexdigest()
                path = os.path.join(BASE_DIR, "cache", "media", key[0], key[1], key)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                if not os.path.exists(path):
                    if mime.startswith("image/"):
                        subprocess.check_call(["/usr/bin/convert", s.phys, f"WEBP:{path}"])
                    else:
                        raise Exception(f"Unsuppored mime {mime} for convert")
                mime = mimedetector.from_file(path)

            with open(path, 'rb') as f:
                res = HttpResponse(f)
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

    base_dir = os.path.dirname(submit.dir())
    dir_a = os.path.join(base_dir, str(submit_a))
    dir_b = os.path.join(base_dir, str(submit_b))

    files_a = os.listdir(dir_a)
    files_b = os.listdir(dir_b)

    def get_patch(p1, p2):
        # python3.7 does not support errors on TemporaryFile
        with tempfile.NamedTemporaryFile('r') as diff:
            subprocess.Popen(["diff", "-ruiwN"] + [p1, p2], cwd=base_dir, stdout=diff).wait()
            with open(diff.name, errors='ignore') as out:
                return out.read()

    # TODO: find better diffing tool that handles file renames
    if len(files_a) == 1 and os.path.isfile(files_a[0]) and len(files_b) == 1 and os.path.isfile(files_b[0]):
        with tempfile.TemporaryDirectory() as p1, tempfile.TemporaryDirectory() as p2:
            with open(os.path.join(p1, "main.c"), 'w') as out:
                with open(os.path.join(dir_a, files_a[0]), errors='ignore') as inp:
                    out.write(inp.read())
            with open(os.path.join(p2, "main.c"), 'w') as out:
                with open(os.path.join(dir_b, files_b[0]), errors='ignore') as inp:
                    out.write(inp.read())

            out = get_patch(p1, p2)
            out = re.sub(r'^(---|\+\+\+) /tmp/[^/]+/', '\\1 ', out, flags=re.M)
    else:
        out = get_patch(str(submit_a), str(submit_b))
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

    def get_comment_type(comment):
        if comment.author == comment.submit.student:
            return 'student'
        return 'teacher'

    notifications = {c.action_object.id: c for c in Notification.objects.filter(
        target_object_id=submit.id,
        target_content_type=ContentType.objects.get_for_model(Submit)
    )}

    def dump_comment(comment):
        notification = notifications.get(comment.id, None)
        unread = False
        notification_id = None
        if notification:
            unread = notification.unread
            notification_id = notification.id

        return {
            'id': comment.id,
            'author': comment.author.get_full_name(),
            'author_id': comment.author.id,
            'text': comment.text,
            'can_edit': comment.author == request.user,
            'type': get_comment_type(comment),
            'unread': unread,
            'notification_id': notification_id,
        }

    if request.method == 'POST':
        data = json.loads(request.body)
        comment = Comment()
        comment.submit = submit
        comment.author = request.user
        comment.text = data['text']
        comment.source = data.get('source', None)
        comment.line = data.get('line', None)
        comment.save()

        notify.send(
            sender=request.user,
            recipient=comment_recipients(submit, request.user),
            verb='added new',
            action_object=comment,
            target=submit,
            public=False,
        )
        return JsonResponse({**dump_comment(comment), 'unread': True})
    elif request.method == 'PATCH':
        data = json.loads(request.body)
        comment = get_object_or_404(Comment, id=data['id'])

        if comment.author != request.user:
            raise PermissionDenied()

        Notification.objects.filter(
            action_object_object_id=comment.id,
            action_object_content_type=ContentType.objects.get_for_model(Comment)
        ).delete()

        if not data['text']:
            return HttpResponse('{}')
        else:
            if comment.text != data['text']:
                comment.text = data['text']
                comment.save()

                notify.send(
                    sender=request.user,
                    recipient=comment_recipients(submit, request.user),
                    verb='updated',
                    action_object=comment,
                    target=submit,
                    public=False,
                )
            return JsonResponse(dump_comment(comment))

    result = {}
    for source in submit.all_sources():
        mime = mimedetector.from_file(source.phys)
        if mime and mime.startswith('image/'):
            SUPPORTED_IMAGES = [
                'image/png',
                'image/jpeg',
                'image/gif',
                'image/webp',
                'image/svg+xml',
            ]

            result[source.virt] = {
                'type': 'img',
                'path': source.virt,
                'src': reverse('submit_source', args=[submit.id, source.virt]) + ('?convert=1' if mime not in SUPPORTED_IMAGES else ''),
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
            content = ''
            error = None
            try:
                if os.path.getsize(source.phys) > 500 * 1024:
                    error = 'File too large'
                with open(source.phys) as f:
                    content = f.read()
            except UnicodeDecodeError:
                error = "source code contains binary data"
            except FileNotFoundError:
                error = "source code not found"

            result[source.virt] = {
                'type': 'source',
                'path': source.virt,
                'content': content,
                'error': error,
                'comments': {},
            }

    # add comments from pipeline
    resultset = get(submit)
    for pipe in resultset['results']:
        for source, comments in pipe.comments.items():
            for comment in comments:
                try:
                    line = min(result[source]['content'].count('\n'), comment['line']) - 1
                    if not any(filter(lambda c: c['text'] == comment['text'], result[source]['comments'].setdefault(line, []))):
                        result[source]['comments'].setdefault(line, []).append({
                            'id': -1,
                            'author': 'Kelvin',
                            'text': comment['text'],
                            'can_edit': False,
                            'type': 'automated',
                            'url': comment.get('url', None),
                        })
                except KeyError as e:
                    logging.exception(e)

    summary_comments = []
    for comment in Comment.objects.filter(submit_id=submit.id).order_by('id'):
        try:
            if not comment.source:
                summary_comments.append(dump_comment(comment))
            else:
                max_lines = result[comment.source]['content'].count('\n')
                line = 0 if comment.line > max_lines else comment.line
                result[comment.source]['comments'].setdefault(comment.line - 1, []).append(dump_comment(comment))
        except KeyError as e:
            logging.exception(e)

    priorities = {
        'video': 0,
        'img': 1,
        'source': 2,
    }
    return JsonResponse({
        'sources': sorted(result.values(), key=lambda f: (priorities[f['type']], f['path'])),
        'summary_comments': summary_comments,
    })

def file_response(file, filename, mimetype):
    response = HttpResponse(file, mimetype)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def raw_test_content(request, task_name, test_name, file):
    task = get_object_or_404(Task, code=task_name)

    tests = create_taskset(task, request.user.username)

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

    deny_files = ['config.yml', 'script.py', 'solution.c', 'solution.cpp']
    if '..' in path or (path in deny_files and not is_teacher(request.user)):
        raise PermissionDenied()

    system_path = os.path.join("tasks", task_name, path)
    if request.method not in ['HEAD', 'GET']:
        if not is_teacher(request.user):
            raise PermissionDenied()

        if request.method == 'PUT':
            os.makedirs(os.path.dirname(system_path), exist_ok=True)
            with open(system_path, 'wb') as f:
                f.write(request.body)

            if path == 'readme.md':
                readme = load_readme(task.code)
                task.name = readme.name
                if not task.name:
                    task.name = task.code
                task.announce = True if readme.announce else False
                task.save()
            return HttpResponse(status=204)
        elif request.method == 'DELETE':
            os.unlink(system_path)
            return HttpResponse(status=204)
        elif request.method == 'MOVE':
            dst = request.headers['Destination']
            if '..' in dst:
                raise PermissionDenied()
            system_dst = os.path.join("tasks", task_name, dst.lstrip('/'))
            os.makedirs(os.path.dirname(system_dst), exist_ok=True)
            shutil.move(system_path, system_dst)
            return HttpResponse(status=204)
        else:
            return HttpResponseBadRequest()

    try:
        with open(system_path, 'rb') as f:
            resp = HttpResponse(f)
            mime = mimedetector.from_file(system_path)
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


# Files with these extensions will be opened in the browser directly
DIRECT_SHOW_EXTENSIONS = [
    ".html",
    ".svg",
    ".png",
    ".jpg"
]

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
                                                content_type='text/html')
                        else:
                            file_content = test.files[file][result_type].open('rb')
                            file_name = f"{result_type}-{file}"
                            extension = os.path.splitext(file)[1]
                            file_mime = mimedetector.from_file(file)

                            if extension in DIRECT_SHOW_EXTENSIONS and file_mime:
                                return HttpResponse(file_content, content_type=file_mime)
                            return file_response(file_content, file_name, "text/plain")
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

@login_required
def ui(request):
    return render(request, 'web/ui.html')
