import dataclasses
import itertools
import os
import io
import csv
import tarfile
import tempfile
import re
import json
import subprocess
import datetime
import shutil
import logging
import traceback

import rq
import logging
from shutil import copyfile
from typing import Dict, List
from collections import OrderedDict

from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone as tz
from django.conf import settings
from django.db.models import Max, Min, Count
from django.core.cache import caches
from django.contrib.contenttypes.models import ContentType

import django_rq
from notifications.signals import notify
from notifications.models import Notification
from unidecode import unidecode

from common.models import Submit, Class, Task, AssignedTask, Subject, assignedtask_results, current_semester_conds, current_semester
from evaluator.results import EvaluationResult
from kelvin.settings import BASE_DIR, MAX_INLINE_CONTENT_BYTES
from evaluator.testsets import TestSet
from common.evaluate import get_meta, evaluate_submit
from common.utils import is_teacher
from common.moss import PlagiarismMatch, enqueue_moss_check, moss_delete_job_from_cache, \
    moss_job_cache_key, moss_result, \
    moss_task_set_opts, \
    moss_task_get_opts
from common.bulk_import import BulkImport, ImportException

from . import statistics
from .utils import file_response


@user_passes_test(is_teacher)
def teacher_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    task_dir = os.path.join(BASE_DIR, "tasks", task.code)

    testset = TestSet(task_dir, get_meta(request.user.username))

    return render(request, 'web/task_detail.html', {
          'task': task,
          'text': testset.load_readme(),
          'inputs': testset,
          'max_inline_content_bytes': MAX_INLINE_CONTENT_BYTES,
    })


def enrich_matches(matches: List[PlagiarismMatch], teacher: User, task: Task) -> List[Dict[str, str]]:
    """
    Converts PlagiarismMatches to dictionaries and adds additional information
    used by the frontend to them.
    """
    classes = Class.objects.current_semester().filter(teacher=teacher, assignedtask__task=task)
    students = {v[0] for v in User.objects.filter(students__in=classes).values_list("username")}
    match_items = []
    for match in matches:
        match_data = dataclasses.asdict(match)
        match_data["teaching"] = match.first.login in students or match.second.login in students
        match_data["first_fullname"] = User.objects.get(
            username=match.first.login
        ).get_full_name()
        match_data["second_fullname"] = User.objects.get(
            username=match.second.login
        ).get_full_name()
        match_items.append(match_data)
    return match_items


@user_passes_test(is_teacher)
def teacher_task_moss_check(request, task_id):
    # clear MOSS notifications
    Notification.objects.filter(
        action_object_object_id=task_id,
        recipient_id=request.user.id,
        verb="plagiarism",
    ).update(unread=False)

    cache = caches['default']
    key_job = moss_job_cache_key(task_id)

    task = get_object_or_404(Task, pk=task_id)

    job_id = cache.get(key_job)
    if job_id:
        refresh = False
        try:
            job = django_rq.jobs.get_job_class().fetch(job_id, connection=django_rq.queues.get_connection())
            status = job.get_status()
            if status == "started":
                refresh = True
            elif status == "queued":
                refresh = True
                status += f" {job.get_position() + 1}"
            elif status == "failed" and job.exc_info:
                status += f"\n{job.exc_info}"
                moss_delete_job_from_cache(task_id)
        except (rq.exceptions.NoSuchJobError, AttributeError) as e:
            moss_delete_job_from_cache(task_id)
            logging.exception(e)
            status = "unknown"
        return render(request, "web/moss.html", {
            "status": status,
            "task": task,
            "refresh": refresh
        })

    if request.method == 'POST':
        enqueue_moss_check(task_id)
        return redirect(request.path_info)

    opts = moss_task_get_opts(task_id)

    if 'percent' in request.GET:
        opts = {
            **opts,
            "percent": int(request.GET.get("percent", 5)),
            "lines": int(request.GET.get("lines", 1)),
            "show_to_students": int(request.GET.get("show_to_students", False)),
        }
        moss_task_set_opts(task_id, opts)

    res = moss_result(task_id, percent=opts['percent'], lines=opts['lines'])
    if not res:
        return render(request, 'web/moss.html', {
            "task": task,
            "has_result": False
        })
    else:
        newer_submit_count = Submit.objects.filter(
            assignment__task_id=task.id,
            created_at__gt=res.started_at
        ).count()
        matches = enrich_matches(res.matches, request.user, task)
        return render(request, "web/moss.html", {
            "has_result": True,
            "success": res.success,
            "log": res.log,
            "matches": matches,
            "graph": res.to_svg(anonymize=False),
            "opts": res.opts,
            "started_at": res.started_at,
            "finished_at": res.finished_at,
            "moss_url": res.url,
            "newer_submit_count": newer_submit_count,
            "task": task,
        })


@user_passes_test(is_teacher)
def teacher_task_moss_graph(request, task_id):
    res = moss_result(task_id)
    if res is None:
        raise Http404
    task = get_object_or_404(Task, pk=task_id)
    graph = res.to_svg(anonymize=True)
    return file_response(graph.encode("utf8"), f"{task.name}-graph.svg", "image/svg+xml")


@user_passes_test(is_teacher)
def submits(request, student_username=None):
    filters = {}
    student_full_name = None
    if student_username:
        filters['student__username'] = student_username
        student_full_name = get_object_or_404(User, username=student_username).get_full_name()

    submits = Submit.objects.filter(**filters).order_by('-id').select_related('student', 'assignment', 'assignment__task')[:100]
    return render(request, "web/submits.html", {
        'submits': submits,
        'student_username': student_username,
        'student_full_name': student_full_name
    })


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
    assignment = get_object_or_404(AssignedTask, pk=assignment_id)

    with tempfile.TemporaryFile(suffix=".tar.gz") as f:
        with tarfile.open(fileobj=f, mode="w:gz") as tar:
            for submit in get_last_submits(assignment_id):
                for source in submit.all_sources():
                    tar.add(source.phys, f"{submit.student.username}/{source.virt}")

        f.seek(0)
        filename = f"{assignment.task.sanitized_name()}_{assignment.clazz.day}{assignment.clazz.time:%H%M}.tar.gz"
        return file_response(f, filename, "application/tar")


def get_assignment_submits(assignment: AssignedTask):
    results = []
    for result in assignedtask_results(assignment):
        submit = None
        if result['submits']:
            if 'accepted_submit_num' in result:
                submit = Submit.objects.get(
                    assignment_id=assignment.id,
                    student__username=result['student'],
                    submit_num=result['accepted_submit_num'],
                )
                score = EvaluationResult(submit.pipeline_path()).test_score()
                result['passed_tests'] = score[0]
                result['total_tests'] = score[1]
        
        results.append((submit, result))
    return results


@user_passes_test(is_teacher)
def show_assignment_submits(request, assignment_id):
    assignment = get_object_or_404(AssignedTask, pk=assignment_id)
    results = get_assignment_submits(assignment)

    return render(request, 'web/submits_show_source.html', {
        'students': results,
    })


@user_passes_test(is_teacher)
def show_task_submits(request, task_id: int):
    assignments = AssignedTask.objects.filter(task_id=task_id)
    results = list(itertools.chain.from_iterable(
        get_assignment_submits(assignment) for assignment in assignments
    ))

    return render(request, 'web/submits_show_source.html', {
        'students': results,
    })


@user_passes_test(is_teacher)
def submit_assign_points(request, submit_id):
    submit = get_object_or_404(Submit, pk=submit_id)

    points = None
    if request.POST['assigned_points'] != '':
        points = float(request.POST['assigned_points'])

    if submit.assigned_points != points:
        notify.send(
                sender=request.user,
                recipient=[submit.student],
                verb='assigned points to',
                action_object=submit,
                important=True,
        )

    submit.assigned_points = points
    submit.save()

    Notification.objects.filter(
        action_object_object_id=submit.id,
        action_object_content_type=ContentType.objects.get_for_model(Submit),
        verb='submitted',
    ).update(unread=False)

    return redirect(request.META.get('HTTP_REFERER', '/'))


def build_score_csv(assignments, filename):
    result = OrderedDict()

    header = ['LOGIN']
    for assignment in assignments:
        header.append(assignment.task.name)

        for record in assignedtask_results(assignment):
            login = record['student']
            if login not in result:
                result[login] = {'LOGIN': login}

            result[login][assignment.task.name] = record['assigned_points'] if 'assigned_points' in record else 0

    with io.StringIO() as out:
        w = csv.DictWriter(out, fieldnames=header)
        w.writeheader()

        for login, row in result.items():
            w.writerow(row)

        return file_response(out.getvalue(), filename, "text/csv")

def build_edison_task_score_csv(student_points: Dict, filename: str):
    """
    Build CSV file importable by Edison system.
    Edison requires delimiter set to `;`.
    """
    with io.StringIO() as out:
        w = csv.writer(out, delimiter=';')
        for student, points in student_points.items():
            w.writerow([student.username, points])

        return file_response(out.getvalue(), filename, "text/csv")


@user_passes_test(is_teacher)
def download_csv_per_assignment(request, assignment_id: int):
    assigned_task = AssignedTask.objects.get(pk=assignment_id)
    csv_filename = f"{assigned_task.task.sanitized_name()}_{assigned_task.clazz.day}{assigned_task.clazz.time:%H%M}.csv"
    return build_score_csv([assigned_task], csv_filename)

@user_passes_test(is_teacher)
def download_csv_per_task(request, task_id: int):
    """
    Students without a submit are excluded.
    """
    task = get_object_or_404(Task, pk=task_id)
    submits = statistics.get_task_submits(task)
    student_points = statistics.get_student_points(submits)

    return build_edison_task_score_csv(student_points, f"{task.sanitized_name()}.csv")

@user_passes_test(is_teacher)
def download_csv_per_class(request, class_id: int):
    clazz = Class.objects.get(pk=class_id)
    return build_score_csv(clazz.assignedtask_set.all(), f"{clazz.subject.abbr}_{clazz.day}{clazz.time:%H%M}.csv")


@user_passes_test(is_teacher)
def all_tasks(request, **kwargs):
    return render(request, 'web/all_tasks.html', {
        'tasks': Task.objects.filter(**kwargs).order_by('-id'),
        'subjects': Subject.objects.all(),
    })


@user_passes_test(is_teacher)
def reevaluate(request, submit_id):
    submit = Submit.objects.get(pk=submit_id)
    try:
        shutil.rmtree(submit.pipeline_path())
    except FileNotFoundError:
        pass
    submit.points = submit.max_points = None
    submit.jobid = evaluate_submit(request, submit).id
    submit.save()
    return redirect(request.META.get('HTTP_REFERER', reverse('submits')) + "#result")

@user_passes_test(is_teacher)
def bulk_import(request):
    res = {}
    if request.method == 'POST':
        create_lectures = request.POST.get('create_lectures', False) == 'on'

        if 'file' in request.FILES:
            try:
                res['users'] = list(BulkImport().run(
                    request.FILES['file'].read().decode('utf-8'),
                    no_lectures=not create_lectures
                ))
                res['count'] = len(res['users'])
            except (ImportException, UnicodeDecodeError) as e:
                res['error'] = e
            except:
                res['error'] = traceback.format_exc()
        else:
            res['error'] = 'No file uploaded'

    return render(request, 'web/teacher/import.html', res)
