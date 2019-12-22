import os
import io
import csv
import tarfile
import tempfile
from shutil import copyfile
from collections import OrderedDict

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.contrib.auth.decorators import user_passes_test
from django.urls import reverse
from django.utils import timezone as tz
from django.conf import settings

import mosspy
import django_rq

from ..task_utils import highlight_code, render_markdown
from common.models import Submit, Class, Task, AssignedTask
from kelvin.settings import BASE_DIR, MAX_INLINE_CONTENT_BYTES
from evaluator.testsets import TestSet
from common.evaluate import get_meta, evaluate_job
from .utils import is_teacher


@user_passes_test(is_teacher)
def teacher_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    task_dir = os.path.join(BASE_DIR, "tasks", task.code)

    return render(request, 'web/task_detail.html', {
          'task': task,
          'text': render_markdown(task_dir, task.code),
          'inputs': TestSet(task_dir, get_meta(request.user)),
          'max_inline_content_bytes': MAX_INLINE_CONTENT_BYTES,
    })


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


@user_passes_test(is_teacher)
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
def download_csv_per_task(request, assignment_id: int):
    assigned_task = AssignedTask.objects.get(pk=assignment_id)

    csv_str = '\n'.join((f'{l},{s}' for l, s in student_scores(assigned_task)))
    response = HttpResponse(csv_str, 'text/csv')
    csv_filename = f"{assigned_task.task.code}_{assigned_task.clazz.code}_success_rate.csv"
    response['Content-Disposition'] = f'attachment; filename="{csv_filename}"'

    return response


@user_passes_test(is_teacher)
def download_csv_per_class(request, class_id: int):
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


@user_passes_test(is_teacher)
def all_tasks(request):
    return render(request, 'web/all_tasks.html', {'tasks': Task.objects.all()})


@user_passes_test(is_teacher)
def reevaluate(request, submit_id):
    submit = Submit.objects.get(pk=submit_id)
    submit.points = submit.max_points = None
    submit.save()
    django_rq.enqueue(evaluate_job, submit)
    return redirect(request.META.get('HTTP_REFERER', reverse('submits')))
