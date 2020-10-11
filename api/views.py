from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.urls import reverse
from common.models import Submit, Class, Task, AssignedTask, Subject, assignedtask_results, current_semester_conds, current_semester, submit_assignment_path
from .models import UserToken
from django.db import transaction
import django_rq
from evaluator.evaluator import evaluate
from common.evaluate import evaluate_job
from django.http import JsonResponse
from django.contrib.auth.decorators import user_passes_test
from common.utils import is_teacher
from common.models import Task, Class, current_semester_conds
from evaluator.testsets import TestSet 
from common.models import current_semester, Subject
from web.task_utils import load_readme
import os
import json
import datetime
import logging
from django.utils.dateparse import parse_datetime

from web.views.teacher import teacher_list 
from common.utils import ldap_search_user

logger = logging.getLogger(__name__)


@user_passes_test(is_teacher)
def tasks_list(request):
    result = []
    for task in Task.objects.all():
        result.append({
            'id': task.id,
            'title': task.name,
            'path': task.code,
        })
    return JsonResponse({'tasks': result})

@user_passes_test(is_teacher)
def class_detail_list(request, **class_conditions):
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
        for assignment in clazz.assignedtask_set.all().order_by('id'):
            assignment_data = {
                'task_id': assignment.task_id,
                'assignment_id': assignment.id,
                'name': assignment.task.name,
                'short_name': assignment.task.code_name(),

                'moss_link': reverse('teacher_task_moss_check', kwargs={'task_id': assignment.task.id}),
                'sources_link': reverse('download_assignment_submits', kwargs={'assignment_id': assignment.id}),
                'csv_link': reverse('download_csv_per_task', kwargs={'assignment_id': assignment.id}),

                'assigned': assignment.assigned,
                'deadline': assignment.deadline,
                'max_points': assignment.max_points,
                'students': {s.username: {'username': s.username} for s in clazz.students.all()}
            }

            for score in assignedtask_results(assignment):
                if 'assigned_points' in score and score['assigned_points'] is not None and int(assignment.max_points or 0) > 0:
                    ratio = max(0, min(1, score['assigned_points'] / assignment.max_points))
                    green = int(ratio * 200)
                    red = int((1 - ratio) * 255)
                    score['color'] = f'#{red:02X}{green:02X}00'
                score['student'] = score['student'].username


                if 'accepted_submit_num' in score:
                    score['link'] = reverse('task_detail', kwargs={
                        'student_username': score['student'],
                        'assignment_id': assignment.id,
                        'submit_num': score['accepted_submit_num'],
                    }) + '#src'
                else:
                    score['link'] = reverse('task_detail', kwargs={
                        'student_username': score['student'],
                        'assignment_id': assignment.id,
                    }) + '#src'
                assignment_data['students'][score['student']] = score

            assignments.append(assignment_data)

        result.append({
            'id': clazz.id,
            'teacher_username': clazz.teacher.username,
            'timeslot': clazz.timeslot,
            'code': clazz.code,
            'subject_abbr': clazz.subject.abbr,
            'task_link': reverse('teacher_task', kwargs={'task_id': assignment.task_id}),
            'csv_link': reverse('download_csv_per_class', kwargs={'class_id': assignment.clazz_id}),
            'assignments': assignments,
            'summary': clazz.summary(),
            'students': list(clazz.students.all().order_by('username').values('username', 'first_name', 'last_name')),
        })

    return JsonResponse({'classes': result})

@user_passes_test(is_teacher)
def subject_list(request, subject_abbr):
    subject = get_object_or_404(Subject, abbr=subject_abbr)

    classes = []
    for clazz in Class.objects.filter(subject__abbr=subject_abbr, **current_semester_conds()):
        classes.append({
            'id': clazz.id,
            'teacher_username': clazz.teacher.username if clazz.teacher else None,
            'timeslot': clazz.timeslot,
            'code': clazz.code,
            'week_offset': clazz.week_offset,
        })


    return JsonResponse({'classes': classes})

@user_passes_test(is_teacher)
def info(request):
    res = {}
    res['user'] = {
        'id': request.user.id,
        'username': request.user.username,
        'name': request.user.get_full_name()
    }

    semester = current_semester();
    res['semester'] = {
        'begin': semester.begin,
        'year': semester.year,
        'winter': semester.winter,
        'abbr': str(semester),
    }

    return JsonResponse(res)

@user_passes_test(is_teacher)
def add_student_to_class(request, class_id):
    clazz = get_object_or_404(Class, id=class_id)

    data = json.loads(request.body.decode('utf-8'))
    username = data['username']

    errors = []

    for username in data['username']:
        username = username.strip().upper()
        user = None
        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist:
            info = ldap_search_user(username)
            if info:
                user = User(**info)
                user.username = username
                user.save()
 
        if user:
            clazz.students.add(user)
        else:
            errors.append(username)


    return JsonResponse({
        'success': not errors,
        'not_found': errors,
    })

@user_passes_test(is_teacher)
def task_detail(request, task_id=None):
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))

        if '..' in data['path']:
            return HttpResponseBadRequest()

        if not task_id:
            task = Task()
            task.subject = Subject.objects.get(abbr=data['path'].split('/')[0])
        else:
            task = Task.objects.get(id=task_id)
            if task.code != data['path']:
                try:
                    os.renames(
                            os.path.join("tasks", task.code),
                            os.path.join("tasks", data['path'])
                    )
                except FileNotFoundError as e:
                    logger.warn(e)

                for assignment in AssignedTask.objects.filter(task_id=task.id):
                    try:
                        os.renames(
                            os.path.join("submits", *submit_assignment_path(assignment), task.code),
                            os.path.join("submits", *submit_assignment_path(assignment), data['path']),
                        )
                    except FileNotFoundError as e:
                        logger.warn(e)

        task.code = data['path']

        os.makedirs(task.dir(), exist_ok=True)
        if not task.name:
            task.name = task.code
        task.save()

        for cl in data['classes']:
            if cl.get('assigned', None):
                AssignedTask.objects.update_or_create(task_id=task.id, clazz_id=cl['id'], defaults={
                    'assigned': parse_datetime(cl['assigned']),
                    'deadline': parse_datetime(cl['deadline']) if cl.get('deadline', None) else None,
                    'max_points': data.get('max_points', None),
                })
            else:
                AssignedTask.objects.filter(task__id=task.id, clazz_id=cl['id']).delete()
    else:
        task = Task.objects.get(id=task_id)

    result = {
        'id': task.id,
        'path': task.code,
        'classes': [],
        'files': {},
        'files_uri': request.build_absolute_uri(reverse('task_asset', kwargs={
            'task_name': task.code,
            'path': '_'
        })).rstrip('_'),
    }

    assigned = AssignedTask.objects.filter(task_id=task.id)
    if assigned:
        result['max_points'] = assigned.first().max_points

    ignore_list = ['.git', '.taskid', '.']
    for root, subdirs, files in os.walk(task.dir()):
        rel = os.path.relpath(root, task.dir())
        node = result['files']
        for path in rel.split('/'):
            if path not in ignore_list:
                if path not in node:
                    node[path] = {
                        'type': 'dir',
                        'files': {},
                    }
                node = node[path]['files']
        for f in files:
            if f not in ignore_list:
                node[f] = {
                    'type': 'file',
                }

    classes = Class.objects.filter(
            subject__abbr=task.subject.abbr,
            teacher__username=request.user.username,
            **current_semester_conds(),
    )
    for clazz in classes:
        item = {
            'id': clazz.id,
            'timeslot': clazz.timeslot,
            'week_offset': -1,
        }

        assigned = AssignedTask.objects.filter(task_id=task.id, clazz_id=clazz.id).first()
        if assigned:
            item['assigned'] = assigned.assigned
            item['deadline'] = assigned.deadline
            item['week_offset'] = clazz.week_offset

        result['classes'].append(item)

    return JsonResponse(result)
 

@csrf_exempt
@transaction.atomic
def submit(request, task_code):
    try:
        s = Submit()
        s.source = request.FILES['solution']
        s.student = request.user
        s.assignment = AssignedTask.objects.get(task__code=task_code, clazz__students__id=request.user.id)
        s.submit_num = Submit.objects.filter(assignment__id=s.assignment.id, student__id=request.user.id).count() + 1
        s.save()

        django_rq.enqueue(evaluate_job, s)
    
        return HttpResponse(request.build_absolute_uri(reverse('task_detail', kwargs={'assignment_id': s.assignment.id})))
    except UserToken.DoesNotExist:
        return HttpResponse('Authorization token not found', status=401)
    except AssignedTask.DoesNotExist:
        return HttpResponse('Task does not exist', status=404)
