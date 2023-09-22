from collections import defaultdict

from django.core import serializers
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.contrib.auth.models import User
from django.urls import reverse
from common.models import Submit, Class, Task, AssignedTask, Semester, Subject, assignedtask_results, current_semester_conds, current_semester, submit_assignment_path
from .models import UserToken
from django.db import transaction
import django_rq
from common.evaluate import evaluate_submit
from django.http import JsonResponse
from django.contrib.auth.decorators import user_passes_test
from common.utils import is_teacher, points_to_color, inbus_search_user, user_from_inbus_person
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
import serde
import shutil
import traceback

import common.bulk_import
from common.bulk_import import ImportException
from common import inbus
from pathlib import Path
from shutil import copytree, ignore_patterns
from django.utils.dateparse import parse_datetime


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
def all_classes(request):
    conds = {}

    if not request.user.is_superuser:
        conds['teacher_id'] = request.user.id

    semesters = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for cl in Class.objects.filter(**conds).select_related('teacher', 'subject', 'semester'):
        sem = str(cl.semester)
        semesters[sem][cl.subject.abbr][cl.teacher.username].append(cl.code)

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

    if 'class' in request.GET:
        class_conditions['code'] = request.GET['class']

    if not request.user.is_superuser:
        class_conditions['teacher_id'] = request.user.id

    classess = Class.objects.filter(**class_conditions)

    result = []
    for clazz in classess.select_related('semester', 'subject', 'teacher'):
        assignments = []
        students = list(clazz.students.all().order_by('username').values('username', 'first_name', 'last_name'))
        for assignment in clazz.assignedtask_set.all().order_by('id').select_related('task'):
            assignment_data = {
                'task_id': assignment.task_id,
                'task_link': reverse('task_detail', kwargs={'login': request.user.username, 'assignment_id': assignment.id}),
                'assignment_id': assignment.id,
                'name': assignment.task.name,
                'short_name': assignment.task.code_name(),

                'moss_link': reverse('teacher_task_moss_check', kwargs={'task_id': assignment.task.id}),
                'sources_link': reverse('download_assignment_submits', kwargs={'assignment_id': assignment.id}),
                'csv_link': reverse('download_csv_per_assignment', kwargs={'assignment_id': assignment.id}),

                'assigned': assignment.assigned,
                'deadline': assignment.deadline,
                'max_points': assignment.max_points,
                'students': {s['username']: {'username': s['username']} for s in students}
            }

            for score in assignedtask_results(assignment, students=[s['username'] for s in students]):
                if 'assigned_points' in score and score['assigned_points'] is not None and int(assignment.max_points or 0) > 0:
                    score['color'] = points_to_color(score['assigned_points'], assignment.max_points)


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
            'students': students,
        })


    days = ['PO', 'UT', 'ST', 'CT', 'PA', 'SO', 'NE']
    def sort_fn(c):
        timeslot = c['timeslot']
        try:
            day = days.index(timeslot[:2])
        except ValueError:
            day = -1
        return c['subject_abbr'], day, int(timeslot[2:])

    result.sort(key=sort_fn)
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


@user_passes_test(is_teacher)
def subjects_all(request) -> JsonResponse:
    """
    Returns list of all subjects.
    """
    subjects = Subject.objects.all()
    subjects_dicts = [ s.as_dict() for s in subjects ]

    resp = {'subjects': subjects_dicts}

    return JsonResponse(resp)


@login_required
def info(request):
    res = {}
    res['user'] = {
        'id': request.user.id,
        'username': request.user.username,
        'name': request.user.get_full_name(),
        'teacher': is_teacher(request.user),
        'is_superuser': request.user.is_superuser,
        'is_staff': request.user.is_staff,
    }

    semester = current_semester()
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
            person_inbus = inbus_search_user(username)
            if person_inbus:
                user = user_from_inbus_person(person_inbus)
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

        plagiarism_key = data.get("plagiarism_key")
        if plagiarism_key is None or plagiarism_key.strip() == "":
            task.plagiarism_key = None
        else:
            task.plagiarism_key = plagiarism_key[:255]

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
            if not tasks_in_path:
                return JsonResponse({
                    'errors': [f'Cannot delete task, maybe you didn\'t save the task first?']
                }) 

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
        'task_link': reverse('teacher_task', kwargs=dict(task_id=task.id)),
        'moss_link': reverse('teacher_task_moss_check', kwargs=dict(task_id=task.id)),
        'plagiarism_key': task.plagiarism_key
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

@user_passes_test(is_teacher)
def reevaluate_task(request, task_id):
    for submit in Submit.objects.filter(assignment__task_id=task_id):
        submit.jobid = evaluate_submit(request, submit).id
        submit.save()

    return JsonResponse({})

@user_passes_test(is_teacher)
def search(request):
    results = [{
        'text': 'All classes',
        'url': '/',
    }]

    semester = current_semester()

    def serialize(o, **kwargs):
        if isinstance(o, Class):
            return [{
                'text': f'Class {o}',
                'url': f'/#/?semester={semester}&teacher={o.teacher.username}&subject={o.subject.abbr}&class={o.code}',
                **kwargs
            }]
        elif isinstance(o, Task):
            detail = {
                'text': f'Task {o.name} ({o.code})',
                'url': f'/teacher/task/{o.id}',
                **kwargs
            }

            edit = {
                'text': f'Edit task {o.name} ({o.code})',
                'url': f'/#/task/edit/{o.id}',
                **kwargs
            }

            return [detail, edit]
        elif isinstance(o, User):
            return [{
                'text': f'Student {o.first_name} {o.last_name} {o.username}',
                'url': f'/submits/{o.username}',
                **kwargs
            }]
        raise Exception(f"Unknown object: {type(o)}")

    conds = {}
    if not request.user.is_superuser:
        conds['assignedtask__clazz__teacher_id'] = request.user.id
    for task in Task.objects.filter(assignedtask__clazz__semester_id=semester.id, **conds):
        results += serialize(task)

    conds = {}
    if not request.user.is_superuser:
        conds['students__teacher_id'] = request.user.id
    for student in User.objects.filter(students__semester_id=semester.id, **conds).distinct('id'):
        results += serialize(student)

    return JsonResponse({
        'results': results,
    })

@user_passes_test(is_teacher)
def transfer_students(request):
    if request.method != 'POST':
        return HttpResponseBadRequest()

    post = json.loads(request.body.decode('utf-8'))
    src = get_object_or_404(Class, pk=post['src_class'])
    dst = get_object_or_404(Class, pk=post['dst_class'])
    student = get_object_or_404(User, username=post['student'])

    # add student to new class
    dst.students.add(student)

    # transfer all tasks
    transfers = []
    for assignment in post['assignments']:
        for submit in Submit.objects.filter(assignment_id=assignment['src_assignment_id'], student_id=student.id):
            prev_dir = submit.dir()
            submit.assignment_id = assignment['dst_assignment_id']

            transfers.append({
                'submit_id': submit.id,
                'before': prev_dir,
                'after': submit.dir(),
            })
            shutil.move(prev_dir, submit.dir())
            submit.save()

    # remove student from previous class
    src.students.remove(student)
        
    return JsonResponse({'transfers': transfers})


@user_passes_test(is_teacher)
def semesters(request):
    semesters = Semester.objects.all()

    semesters_json = serializers.serialize('json', semesters)

    # TODO: When upgrading, see: https://docs.djangoproject.com/en/4.2/ref/request-response/#httpresponse-objects
    # for a way to set content type.
    return HttpResponse(semesters_json,
                        content_type="application/json")




@user_passes_test(is_teacher)
@require_POST
def import_activities(request):
    res = {}
    post = json.loads(request.body.decode('utf-8'))

    semester_id = post['semester_id']
    subject = post['subject']
    activities_id = post['activities']

    activities = [ inbus.inbus.concrete_activity(activity_id) for activity_id in activities_id ]
    semester = Semester.objects.get(pk=semester_id)

    try:
        res['users'] = list(common.bulk_import.run(activities, subject, semester))
        res['count'] = len(res['users'])
    except (ImportException, UnicodeDecodeError) as e:
        res['error'] = e
    except:
        res['error'] = traceback.format_exc()

    # TODO: When upgrading, see: https://docs.djangoproject.com/en/4.2/ref/request-response/#httpresponse-objects
    # for a way to set content type.
    return HttpResponse(serde.json.to_json(res),
                        content_type="application/json")
