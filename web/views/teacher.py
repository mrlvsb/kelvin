import os
import io
import csv
import tarfile
import tempfile
import re
import json
import subprocess
import datetime
import rq
from shutil import copyfile
from collections import OrderedDict

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone as tz
from django.conf import settings
from django.db.models import Max, Min, Count
from django.core.cache import caches

import django_rq
from notifications.signals import notify
from unidecode import unidecode

from common.models import Submit, Class, Task, AssignedTask, Subject, assignedtask_results, current_semester_conds, current_semester
from kelvin.settings import BASE_DIR, MAX_INLINE_CONTENT_BYTES
from evaluator.testsets import TestSet
from common.evaluate import get_meta, evaluate_job
from common.utils import is_teacher
from common.moss import check_task
from web.task_utils import load_readme, process_markdown 

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

@user_passes_test(is_teacher)
def teacher_task_moss_check(request, task_id):
    cache = caches['default']
    key = f'moss.{task_id}'
    key_job = f'moss.job.{task_id}'

    task = get_object_or_404(Task, pk=task_id)

    job_id = cache.get(key_job)
    if job_id:
        try:
            job = django_rq.jobs.get_job_class().fetch(job_id, connection=django_rq.queues.get_connection())
            status = job.get_status()
            if status == 'queued':
                status += f' {job.get_position() + 1}'
        except (rq.exceptions.NoSuchJobError, AttributeError):
            status = 'unknown'
        return render(request, "web/moss.html", {
            "status": status,
            "task": task,
        })

    if request.method == 'POST' or cache.get(key) is None:
        job = django_rq.enqueue(check_task, task_id)
        cache.set(key_job, job.id, timeout=60*60*8)
        return redirect(request.path_info)

    threshold = {
        "percent": int(request.GET.get("percent", 5)),
        "lines": int(request.GET.get("lines", 1)),
    }

    matches = []
    for match in cache.get(key):
        if min(match['first_percent'], match['second_percent']) > threshold['percent']:
            matches.append(match)


    max_percent = 0
    for d in matches:
        percent = max(int(d['first_percent']), int(d['second_percent']))
        if percent > max_percent:
           max_percent = percent

    with tempfile.NamedTemporaryFile("w") as out:
        print("graph G{", file=out)
        for d in matches:
            M = max(float(d['first_percent']), float(d['second_percent']))
            c = 255 - M / max_percent * 255
            color = "#{c:02x}{c:02x}{c:02x}".format(c=int(c))
            print(f"{d['first_login']} -- {d['second_login']} [shape=box, color=\"{color}\", href=\"{d['link']}\", label=\"{M}%\"];", file=out)
        print("}", file=out)
        out.flush()

        graph = subprocess.check_output(["dot", "-T", "svg", out.name]).decode('utf-8')
        graph = re.sub(r'width="[^"]+" height="[^"]+"', '', graph)

        return render(request, 'web/moss.html', {
            "matches": matches,
            "graph": graph,
            "threshold": threshold,
            "task": task,
        })

@user_passes_test(is_teacher)
def all_classes(request):
    return teacher_list(request)

@user_passes_test(is_teacher)
def teacher_list(request, **class_conditions):
    if not class_conditions:
        class_conditions = {}

    if 'teacher_id' not in class_conditions:
        class_conditions['teacher_id'] = request.user.id
    elif class_conditions['teacher_id'] is None:
        del class_conditions['teacher_id']

    current_semester = True
    if 'semester__winter' in class_conditions:
        class_conditions['semester__winter'] = class_conditions['semester__winter'] == 'W'
        current_semester = False

    if current_semester:
        classess = Class.objects.current_semester().filter(**class_conditions)
    else:
        classess = Class.objects.filter(**class_conditions)

    result = []
    for clazz in classess:
        assignments = []
        students = {s.username: {'student': s, 'points': []} for s in clazz.students.all()}

        for assignment in clazz.assignedtask_set.all().order_by('id'):
            assignments.append(assignment)

            for score in assignedtask_results(assignment):
                score['assignment'] = assignment

                if 'assigned_points' in score and score['assigned_points'] is not None and int(assignment.max_points or 0) > 0:
                    ratio = max(0, min(1, score['assigned_points'] / assignment.max_points))
                    green = int(ratio * 200)
                    red = int((1 - ratio) * 255)
                    score['color'] = f'#{red:02X}{green:02X}00'

                students[score['student'].username]['points'].append(score)

        result.append({
            'class': clazz,
            'assignments': assignments,
            'students': sorted([(s['student'], s['points']) for _, s in students.items()], key=lambda s: s[0].username),
        })

    return render(request, 'web/teacher.html', {
        'classes': result,
        'subjects': Subject.objects.filter(class__teacher=request.user.id, **current_semester_conds('class__')).distinct(),
    })

@user_passes_test(is_teacher)
def submits(request, student_username=None):
    filters = {}
    student_full_name = None
    if student_username:
        filters['student__username'] = student_username
        student_full_name = User.objects.get(username=student_username).get_full_name()

    submits = Submit.objects.filter(**filters).order_by('-id')[:100]
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
        response = HttpResponse(f.read(), 'application/tar')
        filename = f"{assignment.task.sanitized_name()}_{assignment.clazz.day}{assignment.clazz.time:%H%M}.tar.gz"
        response['Content-Disposition'] = f'attachment; filename="{unidecode(filename)}"'
        return response


@user_passes_test(is_teacher)
def show_assignment_submits(request, assignment_id):
    assignment = get_object_or_404(AssignedTask, pk=assignment_id)

    results = []
    for result in assignedtask_results(assignment):
        submit = None
        if result['submits']:
            if 'accepted_submit_num' not in result:
                continue
            submit = Submit.objects.get(
                assignment_id=assignment.id,
                student_id=result['student'].id,
                submit_num=result['accepted_submit_num'],
            )
        results.append((submit, result))

    return render(request, 'web/submits_show_source.html', {
        'students': results,
        'assignment': assignment,
    })

@user_passes_test(is_teacher)
def submit_assign_points(request, submit_id):
    submit = get_object_or_404(Submit, pk=submit_id)

    points = None
    if request.POST['assigned_points'] != '':
        points = float(request.POST['assigned_points'])

    if submit.assigned_points != points:
        notify.send(sender=request.user, recipient=[submit.student],
                    verb='assigned points to', action_object=submit)

    submit.assigned_points = points
    submit.save()
    return redirect(request.META.get('HTTP_REFERER', '/'))


def build_score_csv(assignments, filename):
    result = OrderedDict()

    header = ['LOGIN']
    for assignment in assignments:
        header.append(assignment.task.name)

        for record in assignedtask_results(assignment):
            login = record['student'].username
            if login not in result:
                result[login] = {'LOGIN': login}

            result[login][assignment.task.name] = record['assigned_points'] if 'assigned_points' in record else 0

    with io.StringIO() as out:
        w = csv.DictWriter(out, fieldnames=header)
        w.writeheader()

        for login, row in result.items():
            w.writerow(row)

        response = HttpResponse(out.getvalue(), 'text/csv')
        response['Content-Disposition'] = f'attachment; filename="{unidecode(filename)}"'
        return response

@user_passes_test(is_teacher)
def download_csv_per_task(request, assignment_id: int):
    assigned_task = AssignedTask.objects.get(pk=assignment_id)
    csv_filename = f"{assigned_task.task.sanitized_name()}_{assigned_task.clazz.day}{assigned_task.clazz.time:%H%M}.csv"
    return build_score_csv([assigned_task], csv_filename)

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
    submit.points = submit.max_points = None
    submit.jobid = django_rq.enqueue(evaluate_job, submit).id
    submit.save()
    return redirect(request.META.get('HTTP_REFERER', reverse('submits')) + "#result")

@user_passes_test(is_teacher)
def edit_task(request, task_id=None):
    task = Task()
    subject_abbr = request.GET.get('subject_abbr')

    if not task_id and not subject_abbr:
        return HttpResponseBadRequest()

    if task_id:
        task = Task.objects.get(id=task_id)
        subject_abbr = task.subject.abbr

    if request.method == 'POST':
        code = request.POST.get('dir')
        if '..' in code:
            return HttpResponseBadRequest()

        if not task_id:
            task = Task()
            task.subject = Subject.objects.get(abbr=subject_abbr)
        else:
            if task.code != request.POST.get('dir'):
                try:
                    os.rename(
                            os.path.join("tasks", task.code),
                            os.path.join("tasks", request.POST.get('dir'))
                    )
                except FileNotFoundError as e:
                    pass

        task.code = request.POST.get('dir')

        os.makedirs(task.dir(), exist_ok=True)
        readme_path = task.readme_path()
        if not readme_path:
            readme_path = os.path.join(task.dir(), "readme.md")

        with open(readme_path, "w") as f:
            f.write(request.POST.get('text'))

        task.name = load_readme(task.code).name
        if not task.name:
            task.name = task.code
        task.save()

        fields = [
            request.POST.getlist('class'),
            request.POST.getlist('assign_date'),
            request.POST.getlist('assign_time'),
            request.POST.getlist('deadline_date'),
            request.POST.getlist('deadline_time'),
        ]

        max_pts = request.POST.get('max_points')
        if max_pts == '':
            max_pts = None

        for class_id, assign_date, assign_time, deadline_date, deadline_time in zip(*fields):
            #assign = class_id in request.POST.getlist('class_assign')
            assign = assign_date and assign_time
            if assign:
                def to_datetime(date, time):
                    if not date or not time:
                        return None
                    d = datetime.datetime.strptime(date, "%Y-%m-%d")
                    hour, minute = map(int, time.split(':'))
                    return d.replace(hour=hour, minute=minute)

                AssignedTask.objects.update_or_create(task_id=task.id, clazz_id=class_id, defaults={
                    'assigned': to_datetime(assign_date, assign_time),
                    'deadline': to_datetime(deadline_date, deadline_time),
                    'max_points': max_pts,
                })
            else:
                AssignedTask.objects.filter(task__id=task.id, clazz_id=class_id).delete()

        return redirect(reverse('edit_task', kwargs={'task_id': task.id}))

    classes = Class.objects.filter(
            subject__abbr=subject_abbr,
            teacher__username=request.user.username,
            **current_semester_conds(),
    )

    cl = []
    for clazz in classes:
        cl.append({
            "class": clazz,
            "assigned": AssignedTask.objects.filter(task_id=task.id, clazz_id=clazz.id).first() if task_id else None,
        })

    max_points = None
    markdown = ""
    if task_id:
        assigned = AssignedTask.objects.filter(task_id=task.id)
        if assigned:
            max_points = assigned.first().max_points
        markdown = task.markdown()
    else:
        task.code = os.path.join(
                subject_abbr,
                str(current_semester()),
                request.user.username,
        )
        markdown = "# Task title"


    return render(request, "web/edit_task.html", {
        'classes': cl,
        'task': task,
        'max_points': max_points,
        'markdown': markdown,
    })
