import dataclasses
import json
import os
import re
import tarfile
import tempfile
import io
import shutil
import hashlib
from collections import namedtuple
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from typing import List

import django_rq
import rq
import subprocess
import magic
import logging

from django.conf import settings
from django.contrib.auth.models import User
from django.core import signing
from django.utils import timezone as datetime
from django.shortcuts import render, redirect, get_object_or_404, resolve_url
from django.http import HttpResponse, Http404, HttpResponseBadRequest, JsonResponse, FileResponse
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.contrib.contenttypes.models import ContentType
from django.views.decorators.csrf import csrf_exempt

from common.models import Submit, Class, AssignedTask, Task, Comment, assignedtask_results, current_semester
from common.evaluate import evaluate_submit
from common.moss import PlagiarismMatch, moss_result
from web.task_utils import load_readme
from kelvin.settings import BASE_DIR, MAX_INLINE_CONTENT_BYTES, MAX_INLINE_LINES
from evaluator.testsets import TestSet
from common.evaluate import get_meta
from evaluator.results import EvaluationResult, PipeResult
from common.utils import is_teacher

from notifications.signals import notify
from notifications.models import Notification

from .upload import MAX_UPLOAD_FILECOUNT, TooManyFilesError, upload_submit_files
from .utils import file_response

mimedetector = magic.Magic(mime=True)

def is_file_small(path):
    def count_lines(path):
        lines = 0
        with open(path) as f:
            for line in f:
                lines += 1
        return lines
    try:
        return os.path.getsize(path) <= MAX_INLINE_CONTENT_BYTES and count_lines(path) < MAX_INLINE_LINES
    except UnicodeDecodeError:
        # probably a binary file
        return False


@login_required()
def student_index(request):
    result = []

    if 'semester' in request.GET:
        try:
            semester = request.GET['semester']
            if len(semester) != 5:
                return HttpResponseBadRequest()

            year, winter = int(semester[:4]), semester[4] == 'W'
            classess = Class.objects.filter(semester__year=year, semester__winter=winter, students__pk=request.user.id)
        except (ValueError, IndexError):
            return HttpResponseBadRequest()
    else:
        semester = str(current_semester())
        classess = Class.objects.current_semester().filter(students__pk=request.user.id)

    for clazz in classess:
        tasks = []
        max_points = 0
        earned_points = 0
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
                if student['student'] == request.user.username:
                    data = {**data, **student}
            if data.get("assigned_points") is not None:
                earned_points += data.get("assigned_points")
            if assignment.max_points is not None:
                max_points += assignment.max_points

            tasks.append(data)

        result.append({
            'class': clazz,
            'summary': clazz.summary(request.user.username),
            'tasks': tasks,
            'max_points': max_points,
            'earned_points': earned_points,
        })

    semesters = []
    for year, winter in Class.objects.filter(students__pk=request.user.id).values_list('semester__year', 'semester__winter').distinct().order_by('semester__begin', 'semester__winter'):
        semesters.append({
            'label': f'{year}/{year + 1} {"winter" if winter else "summer"}',
            'value': f'{year}{"W" if winter else "S"}',
        })

    return render(request, 'web/index.html', {
        'classes': result,
        'semesters': semesters,
        'selected_semester': semester,
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

JobStatus = namedtuple('JobStatus', ['finished', 'status', 'message'], defaults=[False, '', ''])

def get_submit_job_status(jobid):
    try:
        job = django_rq.jobs.get_job_class().fetch(jobid, connection=django_rq.queues.get_connection())
        status = job.get_status()
        if status == 'queued':
            return JobStatus(finished=False, status=f'in queue: {job.get_position() + 1}')
        elif status == 'started':
            if 'actions' in job.meta and job.meta['actions'] > 0:
                percent = job.meta['current_action'] * 100 // job.meta['actions']
                return JobStatus(finished=False, status=f'evaluating {percent}%')
        elif status == 'finished':
            return JobStatus(finished=True, status=status)
        elif status == 'failed':
            return JobStatus(finished=False, status=status, message=job.exc_info)
        return JobStatus(finished=False, status=status)
    except rq.exceptions.NoSuchJobError:
        return JobStatus(finished=True)
    except AttributeError:
        return JobStatus(finished=False)
    return JobStatus(finished=True)

@login_required()
def pipeline_status(request, submit_id):
    submit = get_object_or_404(Submit, id=submit_id)

    if not is_teacher(request.user) and request.user != submit.student:
        raise PermissionDenied()

    s = get_submit_job_status(submit.jobid)
    return JsonResponse({
        'status': s.status,
        'finished': s.finished,
        'message': s.message if is_teacher(request.user) else '',
    })


@dataclasses.dataclass
class PlagiarismEntry:
    link: str
    lines: int
    student_percent: int
    other_percent: int
    other_login: str


def build_plagiarism_entries(login: str, matches: List[PlagiarismMatch]) -> List[PlagiarismEntry]:
    matches = [m for m in matches if login in (m.first.login, m.second.login)]
    matches = sorted(matches, key=lambda match: match.lines, reverse=True)

    def build(match: PlagiarismMatch) -> PlagiarismEntry:
        (student, other) = (match.first, match.second)
        if login == match.second:
            (student, other) = (other, student)
        return PlagiarismEntry(
            link=match.link,
            lines=match.lines,
            student_percent=student.percent,
            other_percent=other.percent,
            other_login=other.login
        )

    return [build(m) for m in matches]


@login_required()
def task_detail(request, assignment_id, submit_num=None, login=None):
    submits = Submit.objects.filter(
        assignment__pk=assignment_id,
    ).order_by('-id')

    user_is_teacher = is_teacher(request.user)
    if user_is_teacher:
        submits = submits.filter(student__username=login)
    else:
        submits = submits.filter(student__pk=request.user.id)
        if login != request.user.username:
            raise PermissionDenied()

    assignment = get_object_or_404(AssignedTask, id=assignment_id)
    testset = create_taskset(assignment.task, login if login else request.user.username)
    is_announce = False
    if (assignment.assigned > datetime.now() or not assignment.clazz.students.filter(username=request.user.username)) and not user_is_teacher:
        is_announce = True
        if not assignment.task.announce:
            raise Http404()

    data = {
        # TODO: task and deadline can be combined into assignment ad deal with it in template
        'task': assignment.task,
        'assigned': assignment.assigned if is_announce else None,
        'deadline': assignment.deadline,
        'submits': submits,
        'text':  testset.load_readme().announce if is_announce else testset.load_readme(),
        'inputs': None if is_announce else testset,
        'max_inline_content_bytes': MAX_INLINE_CONTENT_BYTES,
        'has_pipeline': bool(testset.pipeline),
        'upload': not user_is_teacher or request.user.username == login,
    }

    current_submit = None
    if submit_num:
        try:
            current_submit = submits.get(submit_num=submit_num)
        except Submit.DoesNotExist:
            raise Http404()
    elif submits:
        current_submit = submits[0]
        return redirect(reverse('task_detail', kwargs={
            'assignment_id': current_submit.assignment_id,
            'submit_num': current_submit.submit_num,
            'login': current_submit.student.username,
        }))

    if current_submit:
        data = {**data, **get(current_submit)}
        has_failure = any(r.failed for r in data["results"])
        data['comment_count'] = current_submit.comment_set.count()

        moss_res = moss_result(current_submit.assignment.task.id)
        if moss_res and (user_is_teacher or moss_res.opts.show_to_students):
            svg = moss_res.to_svg(login=current_submit.student.username, anonymize=not user_is_teacher)
            if svg:
                data['has_pipeline'] = True

                res = PipeResult("plagiarism")
                res.title = "Plagiarism checker"

                prepend = ""
                if is_teacher(request.user):
                    if not moss_res.opts.show_to_students:
                        prepend = "<div class='text-muted'>Not shown to students</div>"
                    prepend += f'<a href="/teacher/task/{current_submit.assignment.task_id}/moss">Change thresholds</a>'

                res.html = f"""
                    {prepend}
                    <style>
                    #plagiarism svg {{
                        width: 100%;
                        height: 300px;
                        border: 1px solid rgba(0,0,0,.125);
                    }}
                    </style>
                    <div id="plagiarism">{svg}</div>
                    <script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@3.6.1/dist/svg-pan-zoom.min.js"></script>
                    <script>
                        document.addEventListener('DOMContentLoaded', () => {{
                            const observer = new MutationObserver((changes) => {{
                                if(changes[0].target.classList.contains('active')) {{
                                    svgPanZoom('#plagiarism svg')
                                }}
                            }});
                            observer.observe(document.querySelector('#plagiarism svg').closest('.tab-pane'), {{
                                attributeFilter: ['class']
                            }});
                        }});
                    </script>
                """
                data['results'].pipelines = [res] + data['results'].pipelines
            if user_is_teacher:
                plagiarisms = build_plagiarism_entries(login, moss_res.matches)
                data["plagiarism_matches"] = plagiarisms

        submit_nums = sorted(submits.values_list('submit_num', flat=True))
        current_idx = submit_nums.index(current_submit.submit_num)
        if current_idx - 1 >= 0:
            data['prev_submit'] = submit_nums[current_idx - 1]
        if current_idx + 1 < len(submit_nums):
            data['next_submit'] = submit_nums[current_idx + 1]

        data['total_submits'] = submits.count()
        data['late_submit'] = assignment.deadline and submits.order_by('id').reverse()[0].created_at > assignment.deadline
        data['diff_versions'] = [(s.submit_num, s.created_at) for s in submits.order_by('id')]

        job_status = get_submit_job_status(current_submit.jobid)

        if not job_status.finished:
            data['job_status'] = True
            result_icon = "line-md:loading-loop"
        else:
            data['job_status'] = False
            if job_status.status == "failed" or has_failure:
                result_icon = "akar-icons:cross"
            else:
                result_icon = "mdi:success-circle-outline"
        data["pipeline_result_icon"] = result_icon

    if request.method == 'POST':
        s = Submit()
        s.student = request.user
        s.assignment = assignment
        s.submit_num = Submit.objects.filter(assignment__id=s.assignment.id,
                                             student__id=request.user.id).count() + 1

        solutions = request.FILES.getlist('solution')
        tmp = request.POST.get('paths', None)
        if tmp:
            paths = [f.rstrip('\r') for f in tmp.split('\n') if f.rstrip('\r')]
        else:
            paths = [f.name for f in solutions]

        try:
            upload_submit_files(s, paths, solutions)
        except TooManyFilesError:
            return HttpResponse(
                f"You have uploaded too many files. The maximum allowed file count is {MAX_UPLOAD_FILECOUNT}.",
                status=400
            )

        # we need submit_id before putting the job to the queue
        s.save()
        s.jobid = evaluate_submit(request, s).id
        s.save()

        # delete previous notifications
        Notification.objects.filter(
            action_object_object_id__in=[str(s.id) for s in submits],
            action_object_content_type=ContentType.objects.get_for_model(Submit),
            verb='submitted',
        ).delete()

        if not is_teacher(request.user):
            notify.send(
                    sender=request.user,
                    recipient=[assignment.clazz.teacher],
                    verb='submitted',
                    action_object=s,
                    important=any([s.assigned_points is not None for s in submits]),
            )

        return redirect(reverse('task_detail', kwargs={
            'login': s.student.username,
            'assignment_id': s.assignment.id,
            'submit_num': s.submit_num
        }) + '#result')
    return render(request, 'web/task_detail.html', data)


@login_required()
def find_task_detail(request, task_id, login=None):
    """
    Tries to find an assignment for a given task and a given student.
    If an assignment is found, redirects to its source code.
    """
    student_id = User.objects.get(username=login).id
    classes = Class.objects.filter(students__in=[student_id])
    assignment = AssignedTask.objects\
        .filter(task_id=task_id, clazz_id__in=classes)\
        .order_by("-assigned")\
        .first()
    if assignment is None:
        raise Http404()
    url = "{}#src".format(resolve_url("task_detail", assignment_id=assignment.id, login=login))
    return redirect(url)


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
                        try:
                            subprocess.check_call(["/usr/bin/convert", s.phys, f"WEBP:{path}"])
                        except subprocess.CalledProcessError as e:
                            path = s.phys
                            logging.exception(e)
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
def submit_diff(request, login, assignment_id, submit_a, submit_b):
    submit = get_object_or_404(Submit,
            assignment_id=assignment_id,
            student__username=login,
            submit_num=submit_a
    )

    if not is_teacher(request.user) and request.user.username != submit.student.username:
        raise PermissionDenied()

    base_dir = os.path.dirname(submit.dir())
    dir_a = os.path.join(base_dir, str(submit_a))
    dir_b = os.path.join(base_dir, str(submit_b))

    files_a = os.listdir(dir_a)
    files_b = os.listdir(dir_b)

    excludes = []
    for root, subdirs, files in [*os.walk(dir_a), *os.walk(dir_b)]:
        for f in files:
            path = os.path.join(root, f)
            mime = mimedetector.from_file(path)
            if mime and not mime.startswith('image/') and not is_file_small(path):
                excludes.append('--exclude')

                p = os.path.relpath(path, base_dir).split('/')[1:]
                excludes.append(os.path.join(*p))

    def get_patch(p1, p2):
        # python3.7 does not support errors on TemporaryFile
        with tempfile.NamedTemporaryFile('r') as diff:
            subprocess.Popen(["diff", "-ruiwN", *excludes] + [p1, p2], cwd=base_dir, stdout=diff).wait()
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

    submits = []
    for s in Submit.objects.filter(assignment_id=assignment_id, student__username=login).order_by('submit_num'):
        submits.append({
            'num': s.submit_num,
            'submitted': s.created_at,
            'points': s.assigned_points,
            'comments': s.comment_set.count()
        })

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
            important=True,
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
            comment.delete()
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
                    important=True,
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
            content_url = None
            error = None

            try:
                if is_file_small(source.phys):
                    with open(source.phys) as f:
                        content = f.read()
                else:
                    content_url = reverse("submit_source", kwargs=dict(submit_id=submit.id, path=source.virt))
            except UnicodeDecodeError:
                error = "The file contains binary data or is not encoded in UTF-8"
            except FileNotFoundError:
                error = "source code not found"

            result[source.virt] = {
                'type': 'source',
                'path': source.virt,
                'content': content,
                'content_url': content_url,
                'error': error,
                'comments': {},
            }

    # add comments from pipeline
    resultset = get(submit)
    for pipe in resultset['results']:
        for source, comments in pipe.comments.items():
            for comment in comments:
                try:
                    line = min(result[source]['content'].count('\n'), int(comment['line'])) - 1
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
                result[comment.source]['comments'].setdefault(line - 1, []).append(dump_comment(comment))
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
        'submits': submits,
        'current_submit': submit.submit_num,
        'deadline': submit.assignment.deadline,
    })


def raw_test_content(request, task_name, test_name, file):
    task = get_object_or_404(Task, code=task_name)

    username = request.user.username
    if is_teacher(request.user) and 'student' in request.GET:
        username = request.GET['student']

    tests = create_taskset(task, username)

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

    username = request.user.username
    if is_teacher(request.user) and 'student' in request.GET:
        username = request.GET['student']

    tests = create_taskset(task, username)

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


def zip_directory(directory: str) -> io.BytesIO:
    zip_buffer = io.BytesIO()

    src_path = Path(directory).expanduser().resolve(strict=True)
    with ZipFile(zip_buffer, "w", ZIP_DEFLATED) as zf:
        for file in src_path.rglob("*"):
            zf.write(file, file.relative_to(src_path.parent))
    return zip_buffer


@login_required
def task_asset(request, task_name, path):
    task = get_object_or_404(Task, code=task_name)
    try:
        check_is_task_accessible(request, task)
    except PermissionDenied:
        if not path.split('/')[-1].startswith('announce.'):
            raise PermissionDenied()

    deny_files = ['config.yml', 'tests.yml', 'script.py', 'solution.c', 'solution.cpp']
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
            try:
                os.unlink(system_path)
            except FileNotFoundError:
                pass
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
            if system_path.endswith('.js'):
                mime = 'text/javascript'
            elif system_path.endswith('.wasm'):
                mime = 'application/wasm'
            if mime:
                resp['Content-Type'] = f"{mime};charset=utf-8"
            return resp
    except FileNotFoundError as e:
        # Download directory as a .zip archive.
        # .tar.gz is also allowed as an extension to keep backwards compatibility
        archive_extensions = ['.tar.gz', '.zip']
        for archive_ext in archive_extensions:
            if system_path.endswith(archive_ext):
                directory = system_path[:-len(archive_ext)]
                if os.path.isdir(directory):
                    name = f"{os.path.basename(directory)}.zip"
                    f = zip_directory(directory)
                    f.seek(0)
                    return file_response(f, name, "application/x-zip")
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
                            file_content = test.files[file][result_type].open('rb').read()
                            file_name = f"{result_type}-{file}"
                            extension = os.path.splitext(file)[1]
                            file_mime = mimedetector.from_buffer(file_content)

                            if extension in DIRECT_SHOW_EXTENSIONS and file_mime:
                                return HttpResponse(file_content, content_type=file_mime)
                            return file_response(file_content, file_name, "text/plain")
    raise Http404()


def submit_download(request, assignment_id, login, submit_num):
    submit = get_object_or_404(Submit,
            assignment_id=assignment_id,
            student__username=login,
            submit_num=submit_num
    )

    if 'token' in request.GET:
        token = signing.loads(request.GET['token'], max_age=3600)
        if token.get('submit_id') != submit.id:
            raise PermissionDenied()
    elif not request.user.is_authenticated:
        return redirect(f'{settings.LOGIN_URL}?next={request.path}')
    elif not is_teacher(request.user) and request.user.username != submit.student.username:
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

@login_required
def ui(request):
    return render(request, 'web/ui.html')


@csrf_exempt
def upload_results(request, assignment_id, submit_num, login):
    submit = get_object_or_404(Submit, assignment_id=assignment_id, submit_num=submit_num, student__username=login)

    token = signing.loads(request.GET.get('token'), max_age=3600)
    if token.get('submit_id') != submit.id:
        raise PermissionDenied()

    result_path = os.path.join(
        'submit_results',
        *submit.path_parts(),
    )

    with tarfile.open(fileobj=io.BytesIO(request.body)) as tar:
        tar.extractall(result_path)

    result  = get(submit)['results']
    for pipe in result.pipelines:
        if 'points' in pipe:
            overwrite = 'points_overwrite' in pipe and pipe.points_overwrite
            if (submit.assigned_points is not None and overwrite) or submit.assigned_points is None:
                submit.assigned_points = pipe.points
                submit.save()

    return JsonResponse({"success": True})


def teacher_task_tar(request, task_id):
    task = get_object_or_404(Task, id=task_id)

    if 'token' in request.GET:
        token = signing.loads(request.GET['token'], max_age=3600)
        if token.get('task_id') != task_id:
            raise PermissionDenied()
    elif not is_teacher(request.user):
        raise PermissionDenied()

    f = tempfile.TemporaryFile()
    with tarfile.open(fileobj=f, mode='w') as tar:
        tar.add(task.dir(), '')
    f.seek(0, io.SEEK_SET)

    res = FileResponse(f)
    res['Content-Type'] = 'application/x-tar'
    return res
