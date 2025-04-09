import dataclasses
import json
import logging
import os
import re
import shutil
import traceback
from collections import defaultdict
from pathlib import Path
from shutil import copytree, ignore_patterns
from typing import Optional, List, Set

import django.http
import serde
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet, Q
from django.http import (
    HttpRequest,
    HttpResponseBadRequest,
)
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, resolve_url
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST

import common.bulk_import
from common.bulk_import import ImportException
from common.evaluate import evaluate_submit
from common.event_log import (
    UserEventModel,
    UserEventLogin,
    UserEventSubmit,
    UserEvent,
    UserEventTaskDisplayed,
)
from common.inbus import inbus
from common.models import (
    Submit,
    Class,
    Task,
    AssignedTask,
    Semester,
    Subject,
    assignedtask_results,
    current_semester,
    submit_assignment_path,
)
from common.submit import SubmitRateLimited, store_submit
from common.upload import MAX_UPLOAD_FILECOUNT, TooManyFilesError
from common.utils import is_teacher, points_to_color, inbus_search_user, user_from_inbus_person

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class SearchParams:
    count: int = None
    start: Optional[int] = None
    order_by: Optional[str] = None
    sort: str = "desc"

    @staticmethod
    def from_request(
        request: HttpRequest,
        max_count: int,
        allowed_order_by_columns: List[str],
        default_order_by: Optional[str],
    ) -> "SearchParams":
        count = max_count
        if "count" in request.GET:
            count = min(max_count, int(request.GET["count"]))

        start = None
        if "start" in request.GET:
            start = int(request.GET["start"])

        order_by = default_order_by
        if "order_column" in request.GET:
            order_req = request.GET["order_column"]
            if order_req in allowed_order_by_columns:
                order_by = order_req

        sort = "desc"
        if request.GET.get("sort") == "asc":
            sort = "asc"
        return SearchParams(count=count, start=start, order_by=order_by, sort=sort)

    def apply(self, query: QuerySet) -> QuerySet:
        if self.order_by is not None:
            if self.sort != "desc":
                order = (self.order_by, "id")
            else:
                order = (f"-{self.order_by}", "-id")

            query = query.order_by(*order)

        if self.start is not None:
            query = query[self.start :]

        if self.count is not None:
            query = query[: self.count]
        return query


@user_passes_test(is_teacher)
def tasks_list_all(request: HttpRequest, subject_abbr: str | None = None):
    result = []
    filters = {}

    params = SearchParams.from_request(
        request,
        max_count=100,
        allowed_order_by_columns=["created_at", "name"],
        default_order_by="created_at",
    )

    if subject_abbr is not None:
        filters["subject__abbr"] = subject_abbr

    if "search" in request.GET:
        filters["name__icontains"] = request.GET["search"]

    if len(filters) == 0:
        tasks = Task.objects.all()
    else:
        tasks = Task.objects.filter(**filters)

    allCount = tasks.count()
    tasks = params.apply(tasks)

    for task in tasks:
        result.append(
            {
                "id": task.pk,
                "title": task.name,
                "path": task.code,
                "subject": task.subject.abbr,
                "date": task.created_at,
                "link": resolve_url("teacher_task", task_id=task.pk),
            }
        )
    return JsonResponse({"tasks": result, "count": allCount})


@user_passes_test(is_teacher)
def student_list(request: HttpRequest):
    params = SearchParams.from_request(
        request, max_count=100, allowed_order_by_columns=[], default_order_by="date_joined"
    )
    params.sort = "asc"
    params.order_by = "username"

    # Only allow searching through students
    users = User.objects.exclude(groups__name="teachers")

    if "search" in request.GET:
        search = request.GET["search"].strip()
        users = users.filter(
            Q(username__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
        )

    user_count = users.count()
    users = params.apply(users)

    result = []
    for user in users:
        result.append({"login": user.username, "name": user.get_full_name()})
    return JsonResponse({"students": result, "count": user_count})


@user_passes_test(is_teacher)
def all_classes(request):
    # https://stackoverflow.com/questions/13844158/sort-week-day-texts
    # {'MO': 0, 'TU': 1, ...}
    day_mapper = {name: val for val, name in enumerate(Class.Day)}
    conds = {}

    if not request.user.is_superuser:
        conds["teacher_id"] = request.user.id

    semesters = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    classes = Class.objects.filter(**conds).select_related("teacher", "subject", "semester")

    classes = sorted(classes, key=lambda klass: (day_mapper[klass.day], klass.time))

    for cl in classes:
        sem = str(cl.semester)
        semesters[sem][cl.subject.abbr][cl.teacher.username].append(cl.code)

    return JsonResponse({"semesters": semesters})


@user_passes_test(is_teacher)
def class_detail_list(request):
    class_conditions = {}

    if "teacher" in request.GET:
        class_conditions["teacher__username"] = request.GET["teacher"]
    if "semester" in request.GET:
        year = request.GET["semester"][:4]
        is_winter = request.GET["semester"][-1] == "W"

        class_conditions["semester__year"] = year
        class_conditions["semester__winter"] = is_winter
    if "subject" in request.GET:
        class_conditions["subject__abbr"] = request.GET["subject"]

    if "class" in request.GET:
        class_conditions["code"] = request.GET["class"]

    if not request.user.is_superuser:
        class_conditions["teacher_id"] = request.user.id

    classess = Class.objects.filter(**class_conditions)

    result = []
    for clazz in classess.select_related("semester", "subject", "teacher"):
        assignments = []
        students = list(
            clazz.students.all().order_by("username").values("username", "first_name", "last_name")
        )
        for assignment in clazz.assignedtask_set.all().order_by("id").select_related("task"):
            assignment_data = {
                "task_id": assignment.task_id,
                "task_link": reverse(
                    "task_detail",
                    kwargs={"login": request.user.username, "assignment_id": assignment.id},
                ),
                "assignment_id": assignment.id,
                "name": assignment.task.name,
                "short_name": assignment.task.code_name(),
                "plagcheck_link": reverse(
                    "teacher_task_plagiarism", kwargs={"task_id": assignment.task.id}
                ),
                "sources_link": reverse(
                    "download_assignment_submits", kwargs={"assignment_id": assignment.id}
                ),
                "csv_link": reverse(
                    "download_csv_per_assignment", kwargs={"assignment_id": assignment.id}
                ),
                "assigned": assignment.assigned,
                "deadline": assignment.deadline,
                "max_points": assignment.max_points,
                "students": {s["username"]: {"username": s["username"]} for s in students},
                "task_type": assignment.task.type,
            }

            for score in assignedtask_results(
                assignment, students=[s["username"] for s in students]
            ):
                if (
                    "assigned_points" in score
                    and score["assigned_points"] is not None
                    and int(assignment.max_points or 0) > 0
                ):
                    score["color"] = points_to_color(
                        score["assigned_points"], assignment.max_points
                    )

                if "accepted_submit_num" in score:
                    score["link"] = (
                        reverse(
                            "task_detail",
                            kwargs={
                                "login": score["student"],
                                "assignment_id": assignment.id,
                                "submit_num": score["accepted_submit_num"],
                            },
                        )
                        + "#src"
                    )
                else:
                    score["link"] = (
                        reverse(
                            "task_detail",
                            kwargs={
                                "login": score["student"],
                                "assignment_id": assignment.id,
                            },
                        )
                        + "#src"
                    )
                assignment_data["students"][score["student"]] = score

            assignments.append(assignment_data)

        result.append(
            {
                "id": clazz.pk,
                "teacher_username": clazz.teacher.username,
                "timeslot": clazz.timeslot,
                "code": clazz.code,
                "subject_abbr": clazz.subject.abbr,
                "csv_link": reverse("download_csv_per_class", kwargs={"class_id": clazz.pk}),
                "assignments": assignments,
                "summary": clazz.summary(request.user.username, show_output=True),
                "students": students,
            }
        )

    days = ["PO", "UT", "ST", "CT", "PA", "SO", "NE"]

    def sort_fn(c):
        timeslot = c["timeslot"]
        try:
            day = days.index(timeslot[:2])
        except ValueError:
            day = -1
        return c["subject_abbr"], day, int(timeslot[2:])

    result.sort(key=sort_fn)
    return JsonResponse({"classes": result})


def find_task_ids_from_events(events: List[UserEvent]) -> Set[int]:
    task_ids = set()
    for event in events:
        match event:
            case UserEventSubmit():
                task_ids.add(event.assigned_task_id)
            case UserEventTaskDisplayed():
                task_ids.add(event.assigned_task_id)
    return task_ids


@user_passes_test(is_teacher)
def event_list(request: HttpRequest, login: str):
    user = get_object_or_404(User, username=login.upper())
    if is_teacher(user):
        raise PermissionDenied()

    params = SearchParams.from_request(
        request,
        max_count=100,
        allowed_order_by_columns=["action", "created_at"],
        default_order_by="created_at",
    )

    query = UserEventModel.objects.filter(user=user)
    event_count = query.count()
    query = params.apply(query)
    events: List[UserEvent] = [event.deserialize() for event in query]

    # Try to provide a bit more useful data by fetching task information from the DB
    # To avoid doing N+1 queries, first find the relevant tasks and then fetch them all at once
    task_ids = find_task_ids_from_events(events)
    tasks = {task.pk: task for task in AssignedTask.objects.filter(id__in=task_ids)}

    result = []
    for event in events:
        action = None
        metadata = dict()
        match event:
            case UserEventLogin():
                action = "login"
            case UserEventSubmit():
                action = "submit"
                metadata["link"] = reverse(
                    "task_detail",
                    kwargs=dict(
                        assignment_id=event.assigned_task_id,
                        login=user.username,
                        submit_num=event.submit_num,
                    ),
                )
                metadata["submit_num"] = event.submit_num
                metadata["task_name"] = tasks[event.assigned_task_id].task.name
            case UserEventTaskDisplayed():
                action = "task-view"
                metadata["link"] = reverse(
                    "task_detail",
                    kwargs=dict(
                        assignment_id=event.assigned_task_id,
                        login=user.username,
                    ),
                )
                metadata["task_name"] = tasks[event.assigned_task_id].task.name
        data = dict(
            action=action,
            metadata=metadata,
            login=event.user.username,
            ip_address=event.ip_address,
            created_at=event.created_at,
        )
        result.append(data)

    return JsonResponse({"events": result, "count": event_count})


@user_passes_test(is_teacher)
def subject_list(request, subject_abbr: str):
    """
    Returns the list of active classes for a given subject.
    Used when creating a new task.
    """
    get_object_or_404(
        Subject, abbr=subject_abbr
    )  # The result is not needed, the call is to provide 404 error

    classes = []
    for clazz in Class.objects.current_semester().filter(subject__abbr=subject_abbr):
        classes.append(
            {
                "id": clazz.pk,
                "teacher": clazz.teacher.username if clazz.teacher else None,
                "timeslot": clazz.timeslot,
                "code": clazz.code,
                "week_offset": clazz.week_offset,
            }
        )

    return JsonResponse({"classes": classes})


@user_passes_test(is_teacher)
def subjects_all(request) -> JsonResponse:
    """
    Returns list of all subjects.
    """
    subjects = Subject.objects.all()
    subjects_dicts = [s.as_dict() for s in subjects]

    resp = {"subjects": subjects_dicts}

    return JsonResponse(resp)


@user_passes_test(is_teacher)
@require_GET
def teachers_all(request) -> JsonResponse:
    teachers = User.objects.filter(groups__name="teachers")
    items = tuple(
        {"username": t.username, "full_name": t.get_full_name(), "last_name": t.last_name}
        for t in teachers
    )

    resp = {"teachers": items}
    return JsonResponse(resp)


@login_required
def info(request):
    res = {}
    res["user"] = {
        "id": request.user.id,
        "username": request.user.username,
        "name": request.user.get_full_name(),
        "teacher": is_teacher(request.user),
        "is_superuser": request.user.is_superuser,
        "is_staff": request.user.is_staff,
    }

    semester = current_semester()
    res["semester"] = {
        "begin": semester.begin,
        "year": semester.year,
        "winter": semester.winter,
        "abbr": str(semester),
        "inbus_semester_id": semester.inbus_semester_id,
    }

    return JsonResponse(res)


@user_passes_test(is_teacher)
def add_student_to_class(request, class_id):
    clazz = get_object_or_404(Class, id=class_id)

    data = json.loads(request.body.decode("utf-8"))
    username = data["username"]

    errors = []

    for username in data["username"]:
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

    return JsonResponse(
        {
            "success": not errors,
            "not_found": errors,
        }
    )


@user_passes_test(is_teacher)
def task_detail(request, task_id=None):
    errors = []
    if request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))

        if ".." in data["path"] or data["path"][0] == "/":
            return JsonResponse(
                {
                    "errors": ["Path should not contain .. or start with /"],
                },
                status=400,
            )

        data["path"] = os.path.normpath(data["path"])
        new_path = os.path.join("tasks", data["path"])

        def set_subject(task):
            subj = data["path"].split("/")[0]
            try:
                task.subject = Subject.objects.get(abbr=subj)
                return None
            except Subject.DoesNotExist:
                return JsonResponse(
                    {
                        "errors": [
                            f'Subject "{subj}" does not exist! Please set correct subject abbr in the path.'
                        ],
                    },
                    status=400,
                )

        if not task_id:
            if Task.objects.filter(code=data["path"]).count() != 0:
                return JsonResponse(
                    {
                        "errors": [f'The task with path "{data["path"]}" already exists.'],
                    },
                    status=400,
                )

            task = Task()

            err = set_subject(task)
            if err:
                return err

            paths = [str(p.parent) for p in Path(new_path).rglob(".taskid")]
            if len(paths) != 0:
                return JsonResponse(
                    {
                        "errors": [
                            f'Cannot create task in the directory "{data["path"]}", because there already exists these tasks:\n{chr(10).join(paths)}'
                        ],
                    },
                    status=400,
                )
        else:
            task = Task.objects.get(id=task_id)

            err = set_subject(task)
            if err:
                return err

            if task.code != data["path"]:
                paths = [str(p.parent) for p in Path(new_path).rglob(".taskid")]
                if len(paths) != 0:
                    return JsonResponse(
                        {
                            "errors": [
                                f'Cannot move task to the directory "{data["path"]}", because there already exists these tasks:\n{chr(10).join(paths)}'
                            ],
                        },
                        status=400,
                    )

                try:
                    os.renames(os.path.join("tasks", task.code), new_path)
                except FileNotFoundError as e:
                    logger.warning(e)

                for assignment in AssignedTask.objects.filter(task_id=task.pk):
                    try:
                        os.renames(
                            os.path.join("submits", *submit_assignment_path(assignment), task.code),
                            os.path.join(
                                "submits", *submit_assignment_path(assignment), data["path"]
                            ),
                        )
                    except FileNotFoundError as e:
                        logger.warning(e)

        task.code = data["path"]
        os.makedirs(task.dir(), exist_ok=True)
        if not task.name:
            task.name = task.code

        plagiarism_key = data.get("plagiarism_key")
        if plagiarism_key is None or plagiarism_key.strip() == "":
            task.plagiarism_key = None
        else:
            task.plagiarism_key = plagiarism_key[:255]

        if data.get("type") in Task.TaskType.values or data.get("type") is None:
            task.type = data.get("type")
        else:
            return JsonResponse(
                {
                    "errors": [f'Invalid task type {data.get("type")}'],
                },
                status=400,
            )

        task.save()

        taskid_path = os.path.join(task.dir(), ".taskid")
        if not os.path.exists(taskid_path):
            with open(taskid_path, "w") as f:
                f.write(str(task.pk))

        for cl in data["classes"]:
            if cl.get("assigned", None):
                AssignedTask.objects.update_or_create(
                    task_id=task.pk,
                    clazz_id=cl["id"],
                    defaults={
                        "assigned": parse_datetime(cl["assigned"]),
                        "deadline": parse_datetime(cl["deadline"])
                        if cl.get("deadline", None)
                        else None,
                        "max_points": cl.get("max_points", None),
                    },
                )
            else:
                submits = Submit.objects.filter(
                    assignment__task_id=task.pk, assignment__clazz_id=cl["id"]
                ).count()
                if submits == 0:
                    AssignedTask.objects.filter(task__id=task.pk, clazz_id=cl["id"]).delete()
                else:
                    clazz = Class.objects.get(id=cl["id"])
                    errors.append(
                        f"Could not deassign from class {str(clazz)}, because it already contains {submits} submits"
                    )
    else:
        task = Task.objects.get(id=task_id)

    if request.method == "DELETE":
        if AssignedTask.objects.filter(task_id=task_id).count():
            return JsonResponse({"errors": ["Cannot delete task - there are assigned classes"]})

        tasks_in_path = [str(p.parent) for p in Path(task.dir()).rglob(".taskid")]
        if len(tasks_in_path) != 1:
            if not tasks_in_path:
                return JsonResponse(
                    {"errors": ["Cannot delete task, maybe you didn't save the task first?"]}
                )

            return JsonResponse(
                {
                    "errors": [
                        f"Cannot delete task - there are multiple taskids:\n{chr(10).join(tasks_in_path)}"
                    ]
                }
            )

        try:
            with open(os.path.join(task.dir(), ".taskid")) as f:
                task_id_in_file = int(f.read().strip())
                if task_id != task_id_in_file:
                    return JsonResponse(
                        {
                            "errors": [
                                f"Cannot delete task - task ID ({task_id}) doesn't match value {task_id_in_file} in the file."
                            ]
                        }
                    )
        except FileNotFoundError:
            return JsonResponse({"errors": ["Cannot delete task - .taskid could not be read"]})

        task.delete()
        shutil.rmtree(task.dir())
        return JsonResponse(
            {
                "success": True,
            }
        )

    result = {
        "id": task.pk,
        "subject_abbr": task.subject.abbr,
        "path": task.code,
        "classes": [],
        "files": {},
        "files_uri": request.build_absolute_uri(
            reverse("task_asset", kwargs={"task_name": task.code, "path": "_"})
        ).rstrip("_"),
        "errors": errors,
        "task_link": reverse("teacher_task", kwargs=dict(task_id=task.pk)),
        "plagcheck_link": reverse("teacher_task_plagiarism", kwargs=dict(task_id=task.pk)),
        "plagiarism_key": task.plagiarism_key,
        "type": task.type,
    }

    ignore_list = [r"\.git", r"^\.taskid$", r"^\.$", r"__pycache__", r"\.pyc$"]
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

        node = result["files"]
        if rel != ".":
            for path in rel.split("/"):
                if path not in node:
                    node[path] = {
                        "type": "dir",
                        "files": {},
                    }
                node = node[path]["files"]

        for f in files:
            if is_allowed(os.path.join(rel, f)):
                node[f] = {
                    "type": "file",
                }

    classes = Class.objects.current_semester().filter(
        subject__abbr=task.subject.abbr,
    )
    assigned_count = 0
    for clazz in classes:
        item = {
            "id": clazz.pk,
            "code": clazz.code,
            "timeslot": clazz.timeslot,
            "week_offset": clazz.week_offset,
            "teacher": clazz.teacher.username,
        }

        assigned = AssignedTask.objects.filter(task_id=task.pk, clazz_id=clazz.pk).first()
        if assigned:
            assigned_count += 1
            item["assignment_id"] = assigned.pk
            item["assigned"] = assigned.assigned
            item["deadline"] = assigned.deadline
            item["max_points"] = assigned.max_points

        result["classes"].append(item)

    result["can_delete"] = assigned_count == 0
    return JsonResponse(result)


@user_passes_test(is_teacher)
def duplicate_task(request, task_id):
    template = get_object_or_404(Task, pk=task_id)

    new_path = template.dir()
    for user in User.objects.filter(groups__name="teachers"):
        new_path = new_path.replace(user.username, request.user.username)

    i = 1
    while os.path.exists(new_path):
        new_path = re.sub(r"(_copy_[0-9]+$|$)", f"_copy_{i}", new_path, count=1)
        i += 1

    copytree(template.dir(), new_path, ignore=ignore_patterns(".taskid"))

    copied_task = template
    copied_task.pk = None
    copied_task.code = Task.path_to_code(new_path)
    copied_task.save()

    return JsonResponse(
        {
            "id": copied_task.pk,
        }
    )


@user_passes_test(is_teacher)
def reevaluate_task(request, task_id):
    for submit in Submit.objects.filter(assignment__task_id=task_id):
        submit.jobid = evaluate_submit(request, submit).id
        submit.save()

    return JsonResponse({})


@user_passes_test(is_teacher)
def transfer_students(request):
    if request.method != "POST":
        return HttpResponseBadRequest()

    post = json.loads(request.body.decode("utf-8"))
    src = get_object_or_404(Class, pk=post["src_class"])
    dst = get_object_or_404(Class, pk=post["dst_class"])
    student = get_object_or_404(User, username=post["student"])

    # add student to new class
    dst.students.add(student)

    # transfer all tasks
    transfers = []
    for assignment in post["assignments"]:
        for submit in Submit.objects.filter(
            assignment_id=assignment["src_assignment_id"], student_id=student.pk
        ):
            prev_dir = submit.dir()
            submit.assignment_id = assignment["dst_assignment_id"]

            transfers.append(
                {
                    "submit_id": submit.pk,
                    "before": prev_dir,
                    "after": submit.dir(),
                }
            )
            shutil.move(prev_dir, submit.dir())
            submit.save()

    # remove student from previous class
    src.students.remove(student)

    return JsonResponse({"transfers": transfers})


@user_passes_test(is_teacher)
def semesters(request):
    semesters = Semester.objects.all()
    semesters = [
        {
            "pk": semester.pk,
            "year": semester.year,
            "winter": semester.winter,
            "inbus_semester_id": semester.inbus_semester_id,
        }
        for semester in semesters
    ]
    return JsonResponse({"semesters": semesters})


@user_passes_test(is_teacher)
@require_POST
def import_activities(request):
    res = {}
    post = json.loads(request.body.decode("utf-8"))

    semester_id = post["semester_id"]
    subject_abbr = post["subject_abbr"]
    activities_id = post["activities"]
    activities_to_teacher = post[
        "activities_to_teacher"
    ]  # activities_to_teacher: when INBUS doesn't provide one, UI user selects one

    activities_to_teacher = {
        int(activity_id): teacher_username
        for activity_id, teacher_username in activities_to_teacher.items()
    }

    activities = [inbus.concrete_activity(activity_id) for activity_id in activities_id]
    activities = [
        concrete_activity for concrete_activity in activities if concrete_activity is not None
    ]
    semester = Semester.objects.get(pk=semester_id)

    try:
        res["users"] = list(
            common.bulk_import.run(
                activities, subject_abbr, semester, request.user, activities_to_teacher
            )
        )
        res["count"] = len(res["users"])
    except (ImportException, UnicodeDecodeError) as e:
        # msg = traceback.TracebackException.from_exception(e).format()
        msg = e.args[0]
        res["error"] = msg
    except BaseException:
        res["error"] = traceback.format_exc()

    return JsonResponse(serde.to_dict(res))


@require_POST
@login_required()
def create_submit(request: django.http.HttpRequest, task_assignment: int) -> JsonResponse:
    assignment: AssignedTask = get_object_or_404(AssignedTask, id=task_assignment)

    try:
        submit = store_submit(request, assignment)
    except TooManyFilesError:
        return JsonResponse(
            {"error": f"Too many files uploaded. Maximum is {MAX_UPLOAD_FILECOUNT}."}, status=400
        )
    except SubmitRateLimited as e:
        return JsonResponse(
            {
                "error": f"You need to wait at least {e.time_until_limit_expires.total_seconds():.0f}s before sending another submit."
            },
            status=400,
        )

    url = (
        reverse(
            "task_detail",
            kwargs={
                "login": submit.student.username,
                "assignment_id": submit.assignment.id,
                "submit_num": submit.submit_num,
            },
        )
        + "#result"
    )
    url = request.build_absolute_uri(url)

    return JsonResponse(
        {
            "submit": {
                "id": submit.submit_num,
                "url": url,
            },
            "task": {"name": assignment.task.name},
        }
    )
