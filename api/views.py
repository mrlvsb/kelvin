from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.urls import reverse
from common.models import Submit, Class, Task, AssignedTask, Semester, Subject, assignedtask_results, current_semester_conds, current_semester, submit_assignment_path
from .models import UserToken
from django.db import transaction
import django_rq
from evaluator.evaluator import evaluate
from common.evaluate import evaluate_job
from django.http import JsonResponse
from django.contrib.auth.decorators import user_passes_test
from common.utils import is_teacher, points_to_color
from common.models import Task, Class, current_semester_conds
from evaluator.testsets import TestSet 
from common.models import current_semester, Subject
from web.task_utils import load_readme
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
import os
import re
import json
import datetime
import logging
import shutil
from pathlib import Path
from shutil import copytree, ignore_patterns
from django.utils.dateparse import parse_datetime

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
def all_classess(request):
    semesters = {}
    conds = {}

    if not request.user.is_superuser:
        conds['teacher_id'] = request.user.id

    for cl in Class.objects.filter(**conds):
        sem = str(cl.semester)
        if sem not in semesters:
            semesters[sem] = {}

        if cl.subject.abbr not in semesters[sem]:
            semesters[sem][cl.subject.abbr] = []
        
        if cl.teacher and cl.teacher.username not in semesters[sem][cl.subject.abbr]:
            semesters[sem][cl.subject.abbr].append(cl.teacher.username)
    
    return JsonResponse({'semesters': semesters})

@user_passes_test(is_teacher)
def class_detail_list(request):
    class_conditions = {}

    if 'teacher' in request.GET:
        class_conditions['teacher__username'] = request.GET['teacher']
    if 'semester' in request.GET:
        year = request.GET['semester'][:4]
        is_winter = request.GET['semester'][-1] == 'W'

        class_conditions['semester__year'] = year
        class_conditions['semester__winter'] = is_winter
    if 'subject' in request.GET:
        class_conditions['subject__abbr'] = request.GET['subject']

    if not request.user.is_superuser:
        class_conditions['teacher_id'] = request.user.id

    classess = Class.objects.filter(**class_conditions)

    result = []
    for clazz in classess:
        assignments = []
        for assignment in clazz.assignedtask_set.all().order_by('id'):
            assignment_data = {
                'task_id': assignment.task_id,
                'task_link': reverse('task_detail', kwargs={'login': request.user.username, 'assignment_id': assignment.id}),
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
                    score['color'] = points_to_color(score['assigned_points'], assignment.max_points)
                score['student'] = score['student'].username


                if 'accepted_submit_num' in score:
                    score['link'] = reverse('task_detail', kwargs={
                        'login': score['student'],
                        'assignment_id': assignment.id,
                        'submit_num': score['accepted_submit_num'],
                    }) + '#src'
                else:
                    score['link'] = reverse('task_detail', kwargs={
                        'login': score['student'],
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
            'csv_link': reverse('download_csv_per_class', kwargs={'class_id': clazz.id}),
            'assignments': assignments,
            'summary': clazz.summary(request.user.username, show_output=True),
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
            'teacher': clazz.teacher.username if clazz.teacher else None,
            'timeslot': clazz.timeslot,
            'code': clazz.code,
            'week_offset': clazz.week_offset,
        })


    return JsonResponse({'classes': classes})

@login_required
def info(request):
    res = {}
    res['user'] = {
        'id': request.user.id,
        'username': request.user.username,
        'name': request.user.get_full_name(),
        'teacher': is_teacher(request.user),
        'is_superuser': request.user.is_superuser,
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
    errors = []
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))

        if '..' in data['path'] or data['path'][0] == '/':
            return JsonResponse({
                'errors': ['Path should not contain .. or start with /'],
            }, status=400)

        data['path'] = os.path.normpath(data['path'])
        new_path = os.path.join("tasks", data['path'])

        def set_subject(task):
            subj = data['path'].split('/')[0]
            try:
                task.subject = Subject.objects.get(abbr=subj)
                return None
            except Subject.DoesNotExist:
                return JsonResponse({
                    'errors': [f'Subject "{subj}" does not exist! Please set correct subject abbr in the path.'],
                }, status=400)

        if not task_id:
            if Task.objects.filter(code=data['path']).count() != 0:
                return JsonResponse({
                    'errors': [f'The task with path "{data["path"]}" already exists.'],
                }, status=400)

            task = Task()
            
            err = set_subject(task)
            if err:
                return err

            paths = [str(p.parent) for p in Path(new_path).rglob(".taskid")]
            if len(paths) != 0:
                return JsonResponse({
                    'errors': [f'Cannot create task in the directory "{data["path"]}", because there already exists these tasks:\n{chr(10).join(paths)}'],
                }, status=400)
        else:
            task = Task.objects.get(id=task_id)

            err = set_subject(task)
            if err:
                return err

            if task.code != data['path']:
                paths = [str(p.parent) for p in Path(new_path).rglob(".taskid")]
                if len(paths) != 0:
                    return JsonResponse({
                        'errors': [f'Cannot move task to the directory "{data["path"]}", because there already exists these tasks:\n{chr(10).join(paths)}'],
                    }, status=400)

                try:
                    os.renames(
                            os.path.join("tasks", task.code),
                            new_path
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

        taskid_path = os.path.join(task.dir(), '.taskid')
        if not os.path.exists(taskid_path):
            with open(taskid_path, "w") as f:
                f.write(str(task.id))

        for cl in data['classes']:
            if cl.get('assigned', None):
                AssignedTask.objects.update_or_create(task_id=task.id, clazz_id=cl['id'], defaults={
                    'assigned': parse_datetime(cl['assigned']),
                    'deadline': parse_datetime(cl['deadline']) if cl.get('deadline', None) else None,
                    'max_points': cl.get('max_points', None),
                })
            else:
                submits = Submit.objects.filter(assignment__task_id=task.id, assignment__clazz_id=cl['id']).count()
                if submits == 0:
                    AssignedTask.objects.filter(task__id=task.id, clazz_id=cl['id']).delete()
                else:
                    clazz = Class.objects.get(id=cl['id'])
                    errors.append(f"Could not deassign from class {str(clazz)}, because it already contains {submits} submits")
    else:
        task = Task.objects.get(id=task_id)

    if request.method == 'DELETE':
        if AssignedTask.objects.filter(task_id=task_id).count():
            return JsonResponse({
                'errors': ['Cannot delete task - there are assigned classess']
            })

        tasks_in_path = [str(p.parent) for p in Path(task.dir()).rglob('.taskid')]
        if len(tasks_in_path) != 1:
            return JsonResponse({
                'errors': [f'Cannot delete task - there are multiple taskids:\n{chr(10).join(tasks_in_path)}']
            })

        try:
            with open(os.path.join(task.dir(), ".taskid")) as f:
                task_id_in_file = int(f.read().strip())
                if task_id != task_id_in_file:
                    return JsonResponse({
                        'errors': [f'Cannot delete task - task ID ({task_id}) doesn\'t match value {task_id_in_file} in the file.']
                    })
        except FileNotFoundError:
            return JsonResponse({
                'errors': ['Cannot delete task - .taskid could not be read']
            })

        task.delete()
        shutil.rmtree(task.dir())
        return JsonResponse({
            "success": True,
        })


    result = {
        'id': task.id,
        'subject_abbr': task.subject.abbr, 
        'path': task.code,
        'classes': [],
        'files': {},
        'files_uri': request.build_absolute_uri(reverse('task_asset', kwargs={
            'task_name': task.code,
            'path': '_'
        })).rstrip('_'),
        'errors': errors,
        'task_link': reverse('teacher_task', kwargs={'task_id': task.id}),
    }

    ignore_list = [
        r'\.git',
        r'^\.taskid$',
        r'^\.$',
        r'__pycache__',
        r'\.pyc$'
    ]
    for root, subdirs, files in os.walk(task.dir()):
        rel = os.path.normpath(os.path.relpath(root, task.dir()))

        def is_allowed(path):
            path = os.path.normpath(path)
            for pattern in ignore_list:
                if re.search(pattern, path):
                    return False
            return True

        if not is_allowed(root):
            continue

        node = result['files']
        if rel != '.':
            for path in rel.split('/'):
                if path not in node:
                    node[path] = {
                        'type': 'dir',
                        'files': {},
                    }
                node = node[path]['files']

        for f in files:
            if is_allowed(os.path.join(rel, f)):
                node[f] = {
                    'type': 'file',
                }

    classes = Class.objects.filter(
            subject__abbr=task.subject.abbr,
            **current_semester_conds(),
    )
    assigned_count = 0
    for clazz in classes:
        item = {
            'id': clazz.id,
            'code': clazz.code,
            'timeslot': clazz.timeslot,
            'week_offset': clazz.week_offset,
            'teacher': clazz.teacher.username,
        }

        assigned = AssignedTask.objects.filter(task_id=task.id, clazz_id=clazz.id).first()
        if assigned:
            assigned_count += 1
            item['assignment_id'] = assigned.id
            item['assigned'] = assigned.assigned
            item['deadline'] = assigned.deadline
            item['max_points'] = assigned.max_points

        result['classes'].append(item)

    result['can_delete'] = assigned_count == 0
    return JsonResponse(result)
 
@user_passes_test(is_teacher)
def duplicate_task(request, task_id):
    template = get_object_or_404(Task, pk=task_id)

    new_path = template.dir()
    for user in User.objects.filter(groups__name='teachers'):
        new_path = new_path.replace(user.username, request.user.username)

    i = 1
    while os.path.exists(new_path):
        new_path = re.sub(r"(_copy_[0-9]+$|$)", f'_copy_{i}', new_path, count=1)
        i += 1

    copytree(template.dir(), new_path, ignore=ignore_patterns('.taskid'))

    copied_task = template
    copied_task.id = None
    copied_task.code = Task.path_to_code(new_path)
    copied_task.save()

    return JsonResponse({
        'id': copied_task.id,
    })