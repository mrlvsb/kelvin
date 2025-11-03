import csv
import io
import itertools
import json
import os
import shutil
import tarfile
import tempfile
from collections import OrderedDict

import django.http

from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from notifications.models import Notification
from notifications.signals import notify

from common.evaluate import evaluate_submit, get_meta
from common.models import (
    AssignedTask,
    Class,
    Submit,
    Task,
    assignedtask_results,
)
from common.utils import is_teacher
from evaluator.results import EvaluationResult
from evaluator.testsets import TestSet
from kelvin.settings import BASE_DIR, MAX_INLINE_CONTENT_BYTES
from quiz.models import Quiz, EnrolledQuiz
from quiz.quiz_utils import quiz_to_html, quiz_assigned_classes
from . import statistics
from .utils import file_response
from serde.json import to_json


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
def submit_assign_points(request, submit_id):
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
def task_list(request):
    """
    Page that renders a Vue component with a list of tasks.
    """
    return render(request, "web/task_list.html")


@user_passes_test(is_teacher)
def student_list(request):
    """
    Page that renders a Vue component with a list of students.
    """
    return render(request, "web/student_list.html")


@user_passes_test(is_teacher)
def student_page(request, login: str):
    """
    Page that renders a Vue component with a detail of a single student.
    """
    login = login.upper()
    student = get_object_or_404(User, username=login)
    if is_teacher(student):
        raise PermissionDenied()

    data = dict(
        login=student.username,
        name=student.get_full_name(),
    )
    return render(request, "web/student_page.html", dict(data=data))


@user_passes_test(is_teacher)
def student_transfer(request):
    """
    Page that renders a Vue component to transfer students between classes.
    """
    return render(request, "web/teacher/student_transfer.html")


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


@user_passes_test(is_teacher)
def quiz_scoring(request, enrolled_id: int):
    """
    Function that renders tool allowing to score student's quiz manually.
    """
    enrolled_quiz = get_object_or_404(EnrolledQuiz, pk=enrolled_id, submitted=True)

    data = dict(
        is_teacher=is_teacher(request.user),
        quiz_id=enrolled_quiz.assigned_quiz.quiz.pk,
        enrolled_id=enrolled_quiz.pk,
        remaining=None,
        scoring=json.dumps(enrolled_quiz.scoring),
        student=enrolled_quiz.student.username,
        answers=json.dumps(enrolled_quiz.submit),
        quiz_html=json.dumps(
            quiz_to_html(enrolled_quiz.assigned_quiz.quiz.src, enrolled_quiz.template.content)
        ),
    )

    return render(request, "web/quiz/quiz.html", dict(data=data))


@user_passes_test(is_teacher)
def quiz_edit(request, quiz_id: int):
    """
    Function that renders quiz edit page, or returns 404 if quiz not exists.
    Raises an Exception if there are multiple assignments of one quiz for one class, which is not allowed.
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)

    data = dict(
        id=quiz.pk,
        assignments=json.dumps(quiz_assigned_classes(quiz, request.user.pk)),
        teacher=request.user.username,
        deletable=quiz.assignedquiz_set.count() == 0,
        quiz_directory=quiz.src,
    )

    return render(request, "web/quiz/quiz_edit.html", dict(data=data))


@user_passes_test(is_teacher)
def quiz_detail(request, quiz_id: int):
    """
    Function that renders detail of a quiz.
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)

    quiz_dto = quiz.get_dto()

    data = dict(
        is_teacher=is_teacher(request.user),
        quiz_id=quiz.pk,
        enrolled_id=None,
        answers=None,
        remaining=None,
        scoring=None,
        student=None,
        quiz_html=json.dumps(quiz_to_html(quiz.src, json.loads(to_json(quiz_dto)))),
    )

    return render(request, "web/quiz/quiz.html", dict(data=data))


@user_passes_test(is_teacher)
def quiz_list(request):
    """
    Function that renders page with all quizzes.
    """
    return render(request, "web/quiz/quiz_list.html")


@user_passes_test(is_teacher)
def quiz_submits(request, quiz_id: int):
    """
    Function that renders page with submits for quiz and its assigned classes.
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)

    return render(
        request,
        "web/quiz/quiz_submit_list.html",
        {
            "quiz_id": quiz.id,
        },
    )
