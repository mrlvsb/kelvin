import errno
import hashlib
import json
import os
import random
import re
from datetime import timedelta
from shutil import copytree, rmtree, ignore_patterns

from django.utils import timezone
from serde.json import from_json, to_json
from serde.yaml import to_yaml
from unidecode import unidecode
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.http import HttpRequest
from django.urls import reverse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, resolve_url

from common.models import Subject
from common.utils import is_teacher
from api.dto import (
    QuizDto,
    UpdateQuizDto,
    QuizCreateDto,
    QuizClassAssignmentsUpdateDto,
    ScoringDto,
    SubmitAnswersDto,
)
from quiz.models import Quiz, AssignedQuiz, EnrolledQuiz, TemplateQuiz
from quiz.quiz_utils import score_quiz, quiz_assigned_classes
from quiz.settings import QUIZ_PATH
from web.markdown_utils import process_markdown
from .utils import MethodNotImplemented
from django.http import (
    HttpResponseBadRequest,
    HttpResponseRedirect,
)


@user_passes_test(is_teacher)
def quiz_yaml(request: HttpRequest, quiz_id: int):
    """
    Function that gets, updates, or delete quiz and its content.
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)

    if request.method == "GET":
        return quiz_yaml_get(request, quiz)
    if request.method == "POST":
        return quiz_yaml_post(request, quiz)
    elif request.method == "DELETE":
        return quiz_yaml_delete(request, quiz)

    return MethodNotImplemented()


def quiz_yaml_get(request: HttpRequest, quiz: Quiz):
    """
    Function to get quiz yaml content
    """
    return JsonResponse({"yaml": quiz.read()})


def quiz_yaml_post(request: HttpRequest, quiz: Quiz):
    """
    Function to create/update quiz
    """
    update_quiz = from_json(UpdateQuizDto, json.loads(request.body.decode("utf-8")))

    if os.path.normpath(update_quiz.quiz_directory) != os.path.normpath(quiz.src):
        try:
            quiz.set_up_directory(update_quiz.quiz_directory)
        except OSError as e:
            if e.errno == errno.EEXIST:
                return JsonResponse({"error": "Directory is used by another quiz."}, status=409)
            raise

    quiz_dto = QuizDto(shuffle=update_quiz.shuffle, questions=update_quiz.questions)

    quiz.write(to_yaml(quiz_dto, allow_unicode=True))

    return JsonResponse({"yaml": quiz.read()})


def quiz_yaml_delete(request: HttpRequest, quiz: Quiz):
    """
    Function to delete quiz
    """
    if quiz.assignedquiz_set.count() == 0:
        quiz.delete()
        rmtree(quiz.get_directory_path())
        return JsonResponse({"redirect": "/"})
    else:
        return JsonResponse({"error": "Quiz has assignments and cannot be deleted."}, status=409)


@login_required
def quiz_results(request: HttpRequest, enrolled_id: int, is_submit: int):
    """
    Function that stores student answers for enrolled quiz.
    """
    if request.method != "POST":
        return MethodNotImplemented()

    enrolled_quiz = get_object_or_404(EnrolledQuiz, pk=enrolled_id)

    if request.user.pk != enrolled_quiz.student.pk:
        return JsonResponse({"error": "Forbidden"}, status=403)

    if enrolled_quiz.submitted:
        return JsonResponse({"error": "Quiz already submitted"}, status=403)

    submit_answers_dto = from_json(SubmitAnswersDto, request.body.decode("utf-8"))

    enrolled_quiz.submit = json.loads(to_json(submit_answers_dto.submit))

    if is_submit:
        enrolled_quiz.submitted = True
        enrolled_quiz.submitted_at = timezone.now()
        score_quiz(enrolled_quiz)
        return JsonResponse({"redirect": "/"})

    enrolled_quiz.save()

    return JsonResponse({"message": "Answers have been saved."})


@user_passes_test(is_teacher)
def quiz_scoring(request: HttpRequest, enrolled_id: int):
    """
    Function that stores quiz scoring.
    """
    if request.method != "POST":
        return MethodNotImplemented()

    enrolled_quiz = get_object_or_404(EnrolledQuiz, pk=enrolled_id)

    scoring_dto = from_json(ScoringDto, request.body.decode("utf-8"))

    teacher = request.user

    if enrolled_quiz.scored_by is None:
        enrolled_quiz.scored_by = teacher
    elif enrolled_quiz.scored_by.pk != teacher.pk:
        return JsonResponse({"error": "Forbidden"}, status=403)

    enrolled_quiz.scoring = json.loads(to_json(scoring_dto.scoring))

    enrolled_quiz.save()

    return JsonResponse({"message": "Scoring has been updated."})


@user_passes_test(is_teacher)
def quiz_assignments(request: HttpRequest, quiz_id: int):
    """
    Function to assign or remove quizzes from classes.
    """
    if request.method != "POST":
        return MethodNotImplemented()

    quiz = get_object_or_404(Quiz, pk=quiz_id)

    update_assignments = from_json(QuizClassAssignmentsUpdateDto, request.body.decode("utf-8"))

    for assignment in update_assignments.assignments:
        if (
            assignment.assigned is not None
            and assignment.deadline is not None
            and assignment.duration is not None
        ):
            # If assignment already exist, update it.
            # Otherwise, create new assignment.
            if assignment.assigned_id is not None:
                assigned_quiz = AssignedQuiz.objects.get(pk=assignment.assigned_id)

                assigned_quiz.deadline = assignment.deadline
                assigned_quiz.assigned = assignment.assigned
                assigned_quiz.duration = assignment.duration
                assigned_quiz.publish_results = assignment.publish_results
            else:
                assigned_quiz = AssignedQuiz.objects.create(
                    clazz_id=assignment.id,
                    quiz_id=quiz.pk,
                    deadline=assignment.deadline,
                    assigned=assignment.assigned,
                    duration=assignment.duration,
                    publish_results=assignment.publish_results,
                )

            assigned_quiz.save()
        else:
            # If the assignment is not complete, it will be deleted if possible.
            if assignment.assigned_id is not None:
                try:
                    assigned_quiz = AssignedQuiz.objects.get(pk=assignment.assigned_id)

                    if assigned_quiz.enrolledquiz_set.count() == 0:
                        assigned_quiz.delete()
                except AssignedQuiz.DoesNotExist:
                    pass

    return JsonResponse(
        {
            "message": "Assignments have been updated.",
            "assignments": quiz_assigned_classes(quiz, request.user.id),
            "quiz_deletable": quiz.assignedquiz_set.count() == 0,
        }
    )


@user_passes_test(is_teacher)
def quiz_question_preview(request: HttpRequest, quiz_id: int):
    """
    Function that convert markdown question to HTML and then returns it.
    """
    if request.method != "POST":
        return MethodNotImplemented()

    quiz = get_object_or_404(Quiz, pk=quiz_id)

    content = json.loads(request.body.decode("utf-8"))

    markdown = process_markdown(quiz.src, content, "quiz")

    return JsonResponse({"html": markdown.content})


@user_passes_test(is_teacher)
def quiz_classes(request: HttpRequest, quiz_id: int):
    """
    Function that returns the list of all classes quiz is assigned to.
    """
    if request.method != "GET":
        return MethodNotImplemented()

    assignments = AssignedQuiz.objects.filter(quiz=quiz_id)

    classes_dto = []

    for assignment in assignments:
        classes_dto.append(
            {
                "classId": assignment.clazz.id,
                "className": str(assignment.clazz),
            }
        )

    return JsonResponse({"classes": classes_dto})


@user_passes_test(is_teacher)
def quiz_add(request: HttpRequest):
    """
    Function that creates a new quiz.
    """
    if request.method != "POST":
        return MethodNotImplemented()

    quiz_create = from_json(QuizCreateDto, request.body.decode("utf-8"))

    subject = Subject.objects.get(abbr=quiz_create.subject)

    abbr = subject.abbr.upper()
    username = request.user.username.upper()
    dir_name = unidecode(quiz_create.name).replace(" ", "_").upper()

    src = os.path.join(QUIZ_PATH, abbr, username)

    postfix = 1

    # Finding a working directory for new quiz, working directory is considered found if generated path doesn't point to
    # existing directory and there is no quiz that have generated path assigned.
    while True:
        # Assign postfix _X to potential new working directory, where X is natural number
        postfix_dir_name = dir_name + "_" + str(postfix)
        disk_dir_src = os.path.join(src, postfix_dir_name)

        count = Quiz.objects.filter(src=os.path.join(abbr, username, postfix_dir_name)).count()

        if count == 0:
            try:
                os.makedirs(disk_dir_src)

                break
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise

        postfix += 1

    quiz = Quiz.objects.create(
        name=quiz_create.name, subject=subject, src=os.path.join(abbr, username, postfix_dir_name)
    )

    quiz.save()

    with open(quiz.get_identifier_path(), "w", encoding="utf-8") as file:
        file.write(str(quiz.pk))

    quiz.write("questions:\n")

    return JsonResponse({"message": "Quiz successfully added."})


@user_passes_test(is_teacher)
def quiz_duplicate(request, quiz_id):
    """
    Function that create a duplicate of the quiz.
    """
    if request.method != "POST":
        return MethodNotImplemented()

    quiz = get_object_or_404(Quiz, pk=quiz_id)
    new_src = quiz.src

    for user in User.objects.filter(groups__name="teachers"):
        new_src = new_src.replace(user.username, request.user.username)

    i = 1

    # Finding a working directory for duplicate of quiz, working directory is considered found if generated path doesn't
    # point to existing directory and there is no quiz that have generated path assigned.
    while True:
        # Assign postfix _copy_X to potential new working directory, where X is natural number
        new_src = re.sub(r"(_copy_[0-9]+$|$)", f"_copy_{i}", new_src, count=1)
        count = Quiz.objects.filter(src=new_src).count()
        if count == 0 and not os.path.exists(os.path.join(QUIZ_PATH, new_src)):
            break
        i += 1

    new_path = os.path.join(QUIZ_PATH, new_src)
    copytree(quiz.get_directory_path(), new_path, ignore=ignore_patterns(".quiz_id"))

    quiz_copy = quiz
    quiz_copy.pk = None
    quiz_copy.src = new_src
    quiz_copy.save()

    with open(quiz_copy.get_identifier_path(), "w", encoding="utf-8") as file:
        file.write(str(quiz_copy.pk))

    return JsonResponse({"id": quiz_copy.pk})


@login_required
def quiz_enroll(request, assigned_quiz_id):
    """
    Function that allows enrolling student to a quiz.
    """
    if request.method != "POST":
        return HttpResponseBadRequest()

    assigned_quiz = get_object_or_404(AssignedQuiz, pk=assigned_quiz_id)

    now = timezone.now()

    # If student is not member of a class, or quiz is not able to be enrolled yet, it redirects to the main page.
    if (
        assigned_quiz.clazz.students.filter(username=request.user.username).count() == 0
        or assigned_quiz.assigned > now
    ):
        return HttpResponseRedirect("/")

    try:
        EnrolledQuiz.objects.get(assigned_quiz=assigned_quiz, student=request.user)

        return JsonResponse({"message": "Quiz can not be enrolled multiple times."}, status=500)
    except EnrolledQuiz.DoesNotExist:
        # If enrolling to quiz is possible, enroll.
        if now <= assigned_quiz.deadline:
            quiz_dto = assigned_quiz.quiz.get_dto()

            id_counter = 1

            for question in quiz_dto.questions:
                question._id = str(id_counter)
                id_counter += 1
                if question.answers is not None:
                    for answer in question.answers:
                        answer._id = str(id_counter)
                        id_counter += 1

            if quiz_dto.shuffle:
                random.shuffle(quiz_dto.questions)

                for question in quiz_dto.questions:
                    if question.answers is not None:
                        random.shuffle(question.answers)

            quiz_json = to_json(quiz_dto, sort_keys=True).encode("utf-8")

            quiz_json_hash = hashlib.sha256(quiz_json).hexdigest()

            try:
                template = TemplateQuiz.objects.get(hash=quiz_json_hash)
            except TemplateQuiz.DoesNotExist:
                template = TemplateQuiz.objects.create(
                    hash=quiz_json_hash,
                    content=json.loads(quiz_json),
                    max_points=sum(map(lambda q: q.points, quiz_dto.questions)),
                )
                template.save()

            deadline = now + timedelta(minutes=assigned_quiz.duration)

            if assigned_quiz.deadline < deadline:
                deadline = assigned_quiz.deadline

            enrolled_quiz = EnrolledQuiz.objects.create(
                assigned_quiz=assigned_quiz,
                template=template,
                student=request.user,
                deadline=deadline,
            )
            enrolled_quiz.save()

            return JsonResponse({"redirect": reverse("quiz_fill")}, status=200)
        else:
            return JsonResponse(
                {"message": "Quiz can not be started yet.", "redirect": "/"}, status=500
            )


@user_passes_test(is_teacher)
def quizzes_list_all(request: HttpRequest, subject_abbr: str | None = None):
    """
    Function that returns the list of quizzes with filtration.
    """

    count = None
    start = None
    order_by = "created_at"
    sort = "desc"

    filters = {}

    if subject_abbr is not None:
        filters["subject__abbr"] = subject_abbr
    if "count" in request.GET:
        count = int(request.GET["count"])
    if "start" in request.GET:
        start = int(request.GET["start"])
    if "sort" in request.GET:
        if request.GET["sort"] == "asc":
            sort = "asc"

    if sort != "desc":
        order = (order_by, "id")
    else:
        order = (f"-{order_by}", "-id")

    if "search" in request.GET:
        filters["name__icontains"] = request.GET["search"]

    quizzes = Quiz.objects.filter(**filters).order_by(*order)

    all_count = quizzes.count()

    if start is not None:
        quizzes = quizzes[start:]

    if count is not None:
        quizzes = quizzes[:count]

    quizzes = list(
        map(
            lambda q: {
                "id": q.pk,
                "name": q.name,
                "subject": q.subject.abbr,
                "date": q.created_at,
                "editLink": resolve_url("quiz_edit", quiz_id=q.pk),
                "submitsLink": resolve_url("quiz_submits", quiz_id=q.pk),
            },
            quizzes,
        )
    )

    return JsonResponse({"quizzes": quizzes, "count": all_count})


@user_passes_test(is_teacher)
def quiz_submits(request: HttpRequest, quiz_id: int, class_id: int | None = None):
    """
    Function that returns the list of quiz submits with filtration.
    """
    count = None
    start = None

    if "count" in request.GET:
        count = int(request.GET["count"])
    if "start" in request.GET:
        start = int(request.GET["start"])

    if class_id is not None:
        assignments = AssignedQuiz.objects.filter(quiz=quiz_id, clazz=class_id)
    else:
        assignments = AssignedQuiz.objects.filter(quiz=quiz_id)

    submits = []

    for assignment in assignments:
        for submit in EnrolledQuiz.objects.filter(assigned_quiz=assignment.id, submitted=True):
            submits.append(submit)

    if start is not None:
        submits = submits[start:]

    if count is not None:
        submits = submits[:count]

    all_count = len(submits)

    submits = list(
        map(
            lambda s: {
                "id": s.pk,
                "classId": s.assigned_quiz.clazz.id,
                "className": str(s.assigned_quiz.clazz),
                "student": s.student.username,
                "score": s.score(),
                "date": s.created_at,
                "scoringLink": resolve_url("quiz_scoring", enrolled_id=s.pk),
            },
            submits,
        )
    )

    return JsonResponse({"submits": submits, "count": all_count})
