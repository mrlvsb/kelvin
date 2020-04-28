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
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone as tz
from django.conf import settings
from django.db.models import Max, Min, Count

import mosspy
import django_rq
from unidecode import unidecode

from ..task_utils import highlight_code
from common.models import Submit, Class, Task, AssignedTask, Subject, assignedtask_results, current_semester_conds
from kelvin.settings import BASE_DIR, MAX_INLINE_CONTENT_BYTES
from evaluator.testsets import TestSet
from common.evaluate import get_meta, evaluate_job
from common.utils import is_teacher

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
    submits = Submit.objects.filter(assignment__task__id=task_id).order_by('-submit_num')
    return redirect(send_to_moss(submits))


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
                    ratio = min(1, score['assigned_points'] / assignment.max_points)
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

def send_to_moss(submits):
    m = mosspy.Moss(settings.MOSS_USERID, "c")

    with tempfile.TemporaryDirectory() as temp_dir:
        processed = set()
        for submit in submits:
            if submit.student_id not in processed:
                dst = os.path.join(temp_dir, f"{submit.student.username}.c")
                with open(dst, "w") as dst_f:
                    for source in submit.all_sources():
                        try:
                            with open(source.phys) as src_f:
                                dst_f.write(src_f.read())
                        except UnicodeDecodeError:
                            # TODO: student can bypass plagiarism check
                            print(submit.student_id)
                m.addFile(dst)

                processed.add(submit.student_id)

        return m.send()

@user_passes_test(is_teacher)
def moss_check(request, assignment_id):
    submits = Submit.objects.filter(assignment_id=assignment_id).order_by('-submit_num')

    assignment = AssignedTask.objects.get(id=assignment_id)
    assignment.moss_url = send_to_moss(submits)
    assignment.save()

    return redirect(assignment.moss_url)


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

    submits = []
    for submit in get_last_submits(assignment_id):
        submits.append(submit)

    submits = sorted(submits, key=lambda submit: submit.student.username)

    return render(request, 'web/submits_show_source.html', {
        'submits': submits,
        'assignment': assignment, 
    })

@user_passes_test(is_teacher)
def submit_assign_points(request, submit_id):
    submit = get_object_or_404(Submit, pk=submit_id)

    points = None
    if request.POST['assigned_points'] != '':
        points = request.POST['assigned_points']

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
    submit.save()
    django_rq.enqueue(evaluate_job, submit)
    return redirect(request.META.get('HTTP_REFERER', reverse('submits')))
