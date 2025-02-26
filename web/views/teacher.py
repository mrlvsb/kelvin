import csv
import dataclasses
import io
import itertools
import os
import shutil
import tarfile
import tempfile
from collections import OrderedDict
from typing import Dict, List, Tuple

import django.http

from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from notifications.models import Notification
from notifications.signals import notify

from common.evaluate import evaluate_submit, get_meta
from common.models import AssignedTask, Class, Submit, Task, assignedtask_results
from common.plagcheck.moss import PlagiarismMatch
from common.utils import is_teacher
from evaluator.results import EvaluationResult
from evaluator.testsets import TestSet
from kelvin.settings import BASE_DIR, MAX_INLINE_CONTENT_BYTES
from . import statistics
from .utils import file_response
from ..emails import send_email_points_assigned


@user_passes_test(is_teacher)
def teacher_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    task_dir = os.path.join(BASE_DIR, "tasks", task.code)

    testset = TestSet(task_dir, get_meta(request.user.username))

    return render(
        request,
        "web/task_detail.html",
        {
            "task": task,
            "text": testset.load_readme(),
            "inputs": testset,
            "max_inline_content_bytes": MAX_INLINE_CONTENT_BYTES,
        },
    )


def enrich_matches(
    matches: List[PlagiarismMatch], teacher: User, task: Task
) -> List[Dict[str, str]]:
    """
    Converts PlagiarismMatches to dictionaries and adds additional information
    used by the frontend to them.
    """

    def get_class_and_link(assignment_id: int, login: str) -> Tuple[str, str]:
        assignment = AssignedTask.objects.get(pk=assignment_id)
        clazz = assignment.clazz
        code = clazz.code
        semester = clazz.semester
        class_str = f"{code} ({semester})"
        link = reverse("find_task_detail", kwargs=dict(task_id=assignment.task.id, login=login))
        return (class_str, link)

    classes = Class.objects.current_semester().filter(teacher=teacher, assignedtask__task=task)
    students = {v[0] for v in User.objects.filter(students__in=classes).values_list("username")}
    match_items = []
    for match in matches:
        match_data = dataclasses.asdict(match)
        match_data["teaching"] = match.first.login in students or match.second.login in students
        match_data["first_fullname"] = User.objects.get(username=match.first.login).get_full_name()

        (first_class, first_link) = get_class_and_link(match.first.assignment_id, match.first.login)
        match_data["first_class"] = first_class
        match_data["first_link"] = first_link
        match_data["second_fullname"] = User.objects.get(
            username=match.second.login
        ).get_full_name()

        (second_class, second_link) = get_class_and_link(
            match.second.assignment_id, match.second.login
        )
        match_data["second_class"] = second_class
        match_data["second_link"] = second_link
        match_items.append(match_data)
    return match_items


@user_passes_test(is_teacher)
def submits(request, student_username=None):
    filters = {}
    student_full_name = None
    if student_username:
        filters["student__username"] = student_username
        student_full_name = get_object_or_404(User, username=student_username).get_full_name()

    submits = (
        Submit.objects.filter(**filters)
        .order_by("-id")
        .select_related("student", "assignment", "assignment__task")[:100]
    )
    return render(
        request,
        "web/submits.html",
        {
            "submits": submits,
            "student_username": student_username,
            "student_full_name": student_full_name,
        },
    )


def get_last_submits(assignment_id):
    submits = Submit.objects.filter(assignment_id=assignment_id).order_by(
        "-submit_num", "student_id"
    )

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
        if result["submits"]:
            if "accepted_submit_num" in result:
                submit = Submit.objects.get(
                    assignment_id=assignment.id,
                    student__username=result["student"],
                    submit_num=result["accepted_submit_num"],
                )
                score = EvaluationResult(submit.pipeline_path()).test_score()
                result["passed_tests"] = score[0]
                result["total_tests"] = score[1]

        results.append((submit, result))
    return results


@user_passes_test(is_teacher)
def show_assignment_submits(request, assignment_id):
    assignment = get_object_or_404(AssignedTask, pk=assignment_id)
    results = get_assignment_submits(assignment)

    return render(
        request,
        "web/submits_show_source.html",
        {
            "students": results,
        },
    )


@user_passes_test(is_teacher)
def show_task_submits(request, task_id: int):
    assignments = AssignedTask.objects.filter(task_id=task_id)
    results = list(
        itertools.chain.from_iterable(
            get_assignment_submits(assignment) for assignment in assignments
        )
    )

    return render(
        request,
        "web/submits_show_source.html",
        {
            "students": results,
        },
    )


@user_passes_test(is_teacher)
def submit_assign_points(request: HttpRequest, submit_id: int):
    submit = get_object_or_404(Submit, pk=submit_id)

    points = None
    if request.POST["assigned_points"] != "":
        points = float(request.POST["assigned_points"])

    if submit.assigned_points != points:
        notify.send(
            sender=request.user,
            recipient=[submit.student],
            verb="assigned points to",
            action_object=submit,
            important=True,
        )
        send_email_points_assigned(
            request=request,
            sender=request.user,
            student=submit.student,
            submit=submit,
            points=points,
        )

    submit.assigned_points = points
    submit.save()

    Notification.objects.filter(
        action_object_object_id=submit.id,
        action_object_content_type=ContentType.objects.get_for_model(Submit),
        verb="submitted",
    ).update(unread=False)

    return redirect(request.META.get("HTTP_REFERER", "/"))


def build_score_csv(assignments, filename: str) -> django.http.HttpResponse:
    result = OrderedDict()

    header = ["LOGIN"]
    for assignment in assignments:
        header.append(assignment.task.name)

        for record in assignedtask_results(assignment):
            login = record["student"]
            if login not in result:
                result[login] = {"LOGIN": login}

            result[login][assignment.task.name] = (
                record["assigned_points"] if "assigned_points" in record else 0
            )

    with io.StringIO() as out:
        w = csv.DictWriter(out, fieldnames=header, delimiter=";")
        w.writeheader()

        for login, row in result.items():
            w.writerow(row)

        return file_response(out.getvalue(), filename, "text/csv")


def build_score_for_assignment_without_header_and_zero_scores_csv(
    assignment: AssignedTask, filename: str
) -> django.http.HttpResponse:
    result = (record for record in assignedtask_results(assignment) if "assigned_points" in record)

    with io.StringIO() as out:
        w = csv.writer(out, delimiter=";")

        for result in result:
            w.writerow([result["student"], result["assigned_points"]])

        return file_response(out.getvalue(), filename, "text/csv")


def build_edison_task_score_csv(student_points, filename: str) -> django.http.HttpResponse:
    """
    Build CSV file importable by Edison system.
    Edison requires delimiter set to `;`.
    """
    with io.StringIO() as out:
        w = csv.writer(out, delimiter=";")
        for student, points in student_points.items():
            w.writerow([student.username, points])

        return file_response(out.getvalue(), filename, "text/csv")


@user_passes_test(is_teacher)
def download_csv_per_assignment(request, assignment_id: int):
    assigned_task = AssignedTask.objects.get(pk=assignment_id)
    csv_filename = f"{assigned_task.task.sanitized_name()}_{assigned_task.clazz.day}{assigned_task.clazz.time:%H%M}.csv"
    return build_score_for_assignment_without_header_and_zero_scores_csv(
        assigned_task, csv_filename
    )


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
    return build_score_csv(
        clazz.assignedtask_set.all(), f"{clazz.subject.abbr}_{clazz.day}{clazz.time:%H%M}.csv"
    )


@user_passes_test(is_teacher)
def all_tasks(request):
    return render(request, "web/all_tasks.html")


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
    return redirect(request.META.get("HTTP_REFERER", reverse("submits")) + "#result")
