import hashlib
import io
import json
import logging
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from collections import namedtuple
from pathlib import Path
from typing import Any, Dict, List, Optional
from zipfile import ZIP_DEFLATED, ZipFile

import django_rq
import magic
import rq
from django.conf import settings
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core import signing
from django.http import (
    FileResponse,
    HttpRequest,
    HttpResponse,
    JsonResponse,
    HttpResponseNotFound,
    HttpResponseRedirect,
)
from django.shortcuts import get_object_or_404, redirect, render, resolve_url
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from common.ai_review.processor import (
    get_submit_review_result,
)
from common.evaluate import get_meta
from common.event_log import record_task_displayed, record_final_submit_event
from common.exceptions.http_exceptions import (
    HttpException400,
    HttpException403,
    HttpException404,
)
from common.models import (
    AssignedTask,
    Class,
    Submit,
    Task,
    assignedtask_results,
    current_semester,
    Comment,
)
from common.plagcheck.moss import PlagiarismMatch, moss_result
from common.submit import SubmitRateLimited, store_submit, SubmitPastHardDeadline, is_file_small
from common.upload import MAX_UPLOAD_FILECOUNT, TooManyFilesError
from common.utils import is_teacher
from evaluator.results import EvaluationResult
from evaluator.testsets import TestSet
from kelvin.settings import BASE_DIR, MAX_INLINE_CONTENT_BYTES
from quiz.models import AssignedQuiz, EnrolledQuiz
from quiz.quiz_utils import quiz_to_html, score_quiz
from quiz.settings import QUIZ_PATH
from web.markdown_utils import load_readme
from .test_script import render_test_script
from .utils import file_response
from ..dto import SubmitData, PlagiarismEntry

mimedetector = magic.Magic(mime=True)


@login_required()
def student_index(request: HttpRequest) -> HttpResponse:
    result = []

    if "semester" in request.GET:
        try:
            semester = request.GET["semester"]
            if len(semester) != 5:
                raise HttpException400()

            year, winter = int(semester[:4]), semester[4] == "W"
            classess = Class.objects.filter(
                semester__year=year, semester__winter=winter, students__pk=request.user.id
            )
        except (ValueError, IndexError):
            raise HttpException400()
    else:
        semester = str(current_semester())
        classess = Class.objects.current_semester().filter(students__pk=request.user.id)

    for clazz in classess:
        tasks = []
        quizzes = []
        max_points = 0
        earned_points = 0
        for assignment in AssignedTask.objects.filter(clazz_id=clazz.id).order_by("-id"):
            if not assignment.task.announce and assignment.assigned > timezone.now():
                continue

            data = {
                "id": assignment.id,
                "name": assignment.task.name,
                "type": assignment.task.get_type_display() if assignment.task.type else None,
                "deadline": assignment.deadline,
                "assigned": assignment.assigned,
                "assigned_show_remaining": assignment.assigned > timezone.now(),
                "assignment": assignment,
            }

            for student in assignedtask_results(assignment, student__id=request.user.id):
                if student["student"] == request.user.username:
                    data = {**data, **student}
            if data.get("assigned_points") is not None:
                earned_points += data.get("assigned_points")
            if assignment.max_points is not None:
                max_points += assignment.max_points

            tasks.append(data)
        for assigned_quiz in AssignedQuiz.objects.filter(clazz_id=clazz.id).order_by("-id"):
            if assigned_quiz.assigned > timezone.now():
                continue

            try:
                enrolled_quiz = EnrolledQuiz.objects.get(
                    assigned_quiz=assigned_quiz, student=request.user, submitted=True
                )
            except EnrolledQuiz.DoesNotExist:
                enrolled_quiz = None

            if enrolled_quiz is None or not assigned_quiz.publish_results:
                try:
                    quiz_max = assigned_quiz.max_points()
                except Exception:
                    continue

                max_points += quiz_max

                data = {
                    "assignment_id": assigned_quiz.id,
                    "name": assigned_quiz.quiz.name,
                    "student": request.user.username,
                    "max_points": quiz_max,
                    "earned_points": None,
                    "deadline": assigned_quiz.deadline,
                    "assigned": assigned_quiz.assigned,
                    "enrolled": enrolled_quiz is not None,
                    "publishable": False,
                }
            else:
                earned = enrolled_quiz.score()

                earned_points += earned

                max_points += enrolled_quiz.template.max_points

                data = {
                    "assignment_id": assigned_quiz.id,
                    "name": assigned_quiz.quiz.name,
                    "student": request.user.username,
                    "max_points": enrolled_quiz.template.max_points,
                    "earned_points": earned,
                    "deadline": assigned_quiz.deadline,
                    "assigned": assigned_quiz.assigned,
                    "enrolled": True,
                    "publishable": True,
                    "enrolled_id": enrolled_quiz.pk,
                }

            quizzes.append(data)

        result.append(
            {
                "class": clazz,
                "summary": clazz.summary(request.user.username),
                "tasks": tasks,
                "quizzes": quizzes,
                "max_points": max_points,
                "earned_points": earned_points,
            }
        )

    semesters = []
    for year, winter in (
        Class.objects.filter(students__pk=request.user.id)
        .values_list("semester__year", "semester__winter")
        .distinct()
        .order_by("semester__begin", "semester__winter")
    ):
        semesters.append(
            {
                "label": f'{year}/{year + 1} {"winter" if winter else "summer"}',
                "value": f'{year}{"W" if winter else "S"}',
            }
        )

    return render(
        request,
        "web/index.html",
        {
            "classes": result,
            "semesters": semesters,
            "selected_semester": semester,
        },
    )


def get_submit_data(submit: Submit) -> SubmitData:
    results = []

    try:
        results = EvaluationResult(submit.pipeline_path())
    except json.JSONDecodeError:
        # TODO: show error
        pass

    return SubmitData(
        submit=submit,
        results=results,
        ai_review=get_submit_review_result(submit),
    )


JobStatus = namedtuple("JobStatus", ["finished", "status", "message"], defaults=[False, "", ""])


def get_submit_job_status(jobid: str | None) -> JobStatus:
    try:
        job = django_rq.jobs.get_job_class().fetch(
            jobid, connection=django_rq.queues.get_connection()
        )
        status = job.get_status()
        if status == "queued":
            position = job.get_position()
            if position is None:
                position = "unknown"
            else:
                position = str(position + 1)
            return JobStatus(finished=False, status=f"in queue: {position}")
        elif status == "started":
            if "actions" in job.meta and job.meta["actions"] > 0:
                percent = job.meta["current_action"] * 100 // job.meta["actions"]
                return JobStatus(finished=False, status=f"evaluating {percent}%")
        elif status == "finished":
            return JobStatus(finished=True, status=status)
        elif status == "failed":
            return JobStatus(finished=False, status=status, message=job.exc_info)
        return JobStatus(finished=False, status=status)
    except rq.exceptions.NoSuchJobError:
        return JobStatus(finished=True)
    except AttributeError:
        return JobStatus(finished=False)
    return JobStatus(finished=True)


@login_required()
def pipeline_status(request: HttpRequest, submit_id: int) -> JsonResponse:
    submit = get_object_or_404(Submit, id=submit_id)

    if not is_teacher(request.user) and request.user != submit.student:
        raise HttpException403()

    s = get_submit_job_status(submit.jobid)
    return JsonResponse(
        {
            "status": s.status,
            "finished": s.finished,
            "message": s.message if is_teacher(request.user) else "",
        }
    )


def build_plagiarism_entries(login: str, matches: List[PlagiarismMatch]) -> List[PlagiarismEntry]:
    matches = [m for m in matches if login in (m.first.login, m.second.login)]
    matches = sorted(matches, key=lambda match: match.lines, reverse=True)

    def build(match: PlagiarismMatch) -> PlagiarismEntry:
        (student, other) = (match.first, match.second)

        if login == match.second.login:
            (student, other) = (other, student)

        return PlagiarismEntry(
            link=match.link,
            lines=match.lines,
            student_percent=student.percent,
            other_percent=other.percent,
            other_login=other.login,
        )

    return [build(m) for m in matches]


@login_required()
def task_detail(
    request: HttpRequest,
    assignment_id: int,
    submit_num: int | None = None,
    login: str | None = None,
) -> HttpResponse:
    submits = Submit.objects.filter(
        assignment__pk=assignment_id,
    ).order_by("-id")

    user_is_teacher = is_teacher(request.user)
    if user_is_teacher:
        submits = submits.filter(student__username=login)
    else:
        submits = submits.filter(student__pk=request.user.id)
        if login != request.user.username:
            raise HttpException403()

    assignment = get_object_or_404(AssignedTask, id=assignment_id)
    testset = create_taskset(
        assignment.task,
        login if login else request.user.username,
        meta=dict(assignment=assignment.id),
    )

    is_announce = False
    if assignment.assigned > timezone.now() and not user_is_teacher:
        is_announce = True
        if not assignment.task.announce:
            raise HttpException404()

    if not user_is_teacher and request.method == "GET":
        record_task_displayed(request, request.user, task=assignment)

    hard_deadline = assignment.hard_deadline and not user_is_teacher

    data = {
        # TODO: task and deadline can be combined into assignment ad deal with it in template
        "task": assignment.task,
        "teacher": assignment.clazz.teacher.username,
        "assigned": assignment.assigned if is_announce else None,
        "deadline": assignment.deadline,
        "now": timezone.now(),
        "hard_deadline": hard_deadline,
        "submits": submits,
        "multiple_ip_addresses": len(set(s.ip_address for s in submits)) > 1,
        "text": testset.load_readme().announce if is_announce else testset.load_readme(),
        "inputs": None if is_announce else testset,
        "max_inline_content_bytes": MAX_INLINE_CONTENT_BYTES,
        "has_pipeline": bool(testset.pipeline),
        "upload": (not user_is_teacher or request.user.username == login)
        and not (hard_deadline and assignment.is_past_deadline()),
    }

    # Provide a link to a student with the same assignment who doesn't yet have any assigned points
    # The order is determined by login, same as in class detail.
    # If there is no "following" student, the ordering wraps back to the beginning of the
    # unevaluated list of students
    if user_is_teacher and login is not None:
        assignment_results = assignedtask_results(assignment)
        unevaluated_students = [
            s
            for s in assignment_results
            if s["submits"] > 0 and s["submits_with_assigned_pts"] == 0 and s["student"] != login
        ]
        unevaluated_students = sorted(unevaluated_students, key=lambda s: s["student"])
        if len(unevaluated_students) > 0:
            next_by_order = [s["student"] for s in unevaluated_students if s["student"] > login]
            if len(next_by_order) > 0:
                next_student_to_evaluate = next_by_order[0]
            else:
                next_student_to_evaluate = unevaluated_students[0]["student"]
            data["next_url_to_evaluate"] = reverse(
                task_detail,
                kwargs=dict(assignment_id=assignment.id, login=next_student_to_evaluate),
            )

    current_submit = None
    if submit_num:
        try:
            current_submit = submits.get(submit_num=submit_num)
        except Submit.DoesNotExist:
            raise HttpException404()
    elif submits:
        current_submit = submits[0]
        return redirect(
            reverse(
                "task_detail",
                kwargs={
                    "assignment_id": current_submit.assignment_id,
                    "submit_num": current_submit.submit_num,
                    "login": current_submit.student.username,
                },
            )
        )

    if current_submit:
        submit_data = get_submit_data(current_submit)
        data = {
            **data,
            "submit": current_submit,
            "results": submit_data.results,
            "review": submit_data.ai_review,
        }

        has_failure = any(r.failed for r in data["results"])
        data["comment_count"] = current_submit.comment_set.count()

        moss_res = moss_result(current_submit.assignment.task.id)
        if moss_res is not None and user_is_teacher:
            plagiarisms = build_plagiarism_entries(login, moss_res.matches)
            data["plagiarism_matches"] = plagiarisms

        submit_nums = sorted(submits.values_list("submit_num", flat=True))
        current_idx = submit_nums.index(current_submit.submit_num)
        if current_idx - 1 >= 0:
            data["prev_submit"] = submit_nums[current_idx - 1]
        if current_idx + 1 < len(submit_nums):
            data["next_submit"] = submit_nums[current_idx + 1]

        data["total_submits"] = submits.count()
        data["late_submit"] = (
            assignment.deadline
            and submits.order_by("id").reverse()[0].created_at > assignment.deadline
        )
        data["diff_versions"] = [(s.submit_num, s.created_at) for s in submits.order_by("id")]

        job_status = get_submit_job_status(current_submit.jobid)

        if not job_status.finished:
            data["job_status"] = True
            result_icon = "line-md:loading-loop"
        else:
            data["job_status"] = False
            if job_status.status == "failed" or has_failure:
                result_icon = "akar-icons:cross"
            else:
                result_icon = "mdi:success-circle-outline"
        data["pipeline_result_icon"] = result_icon

    if request.method == "POST":
        try:
            submit = store_submit(request, assignment)
        except TooManyFilesError:
            return JsonResponse(
                {
                    "error": f"You have uploaded too many files. The maximum allowed file count is {MAX_UPLOAD_FILECOUNT}.",
                },
                status=400,
            )
        except SubmitRateLimited as e:
            # We show an error so that users can re-send the same submit with F5.
            # It can be spammy, but probably better than forcing them to select the files
            # repeatedly.
            return JsonResponse(
                {
                    "error": f"Too many submits. You need to wait {e.time_until_limit_expires.total_seconds():.0f}s before sending another submit",
                    "retry_after": e.time_until_limit_expires.total_seconds(),
                },
                status=429,
            )
        except SubmitPastHardDeadline:
            return JsonResponse(
                {
                    "error": "Your submit was sent after the hard deadline, which is not allowed for this task.",
                },
                status=409,
            )

        return redirect(
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
    return render(request, "web/task_detail.html", data)


@login_required()
def find_task_detail(request: HttpRequest, task_id: int, login: str | None = None):
    """
    Tries to find an assignment for a given task and a given student.
    If an assignment is found, redirects to its source code.
    """
    student_id = User.objects.get(username=login).id
    classes = Class.objects.filter(students__in=[student_id])
    assignment = (
        AssignedTask.objects.filter(task_id=task_id, clazz_id__in=classes)
        .order_by("-assigned")
        .first()
    )
    if assignment is None:
        raise HttpException404()
    url = "{}#src".format(resolve_url("task_detail", assignment_id=assignment.id, login=login))
    return redirect(url)


def comment_recipients(submit: Submit, current_author: User) -> List[User]:
    recipients = [submit.assignment.clazz.teacher, submit.student]

    # add all participants
    for comment in Comment.objects.filter(submit_id=submit.pk):
        if comment.author not in recipients:
            recipients.append(comment.author)

    recipients.remove(current_author)
    return recipients


@login_required
def submit_source(request: HttpRequest, submit_id: int, path: str) -> HttpResponse:
    submit = get_object_or_404(Submit, id=submit_id)
    if not is_teacher(request.user) and request.user.username != submit.student.username:
        raise HttpException403()

    for s in submit.all_sources():
        if s.virt == path:
            path = s.phys
            mime = mimedetector.from_file(s.phys)
            if request.GET.get("convert", False):
                key = hashlib.sha1(f"{submit_id}{path}".encode("utf-8")).hexdigest()
                path = os.path.join(BASE_DIR, "cache", "media", key[0], key[1], key)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                if not os.path.exists(path):
                    if mime.startswith("image/"):
                        try:
                            subprocess.check_call(["/usr/bin/convert", s.phys, f"WEBP:{path}"])
                        except subprocess.CalledProcessError as e:
                            path = s.phys
                            logging.exception(e)
                    else:
                        raise Exception(f"Unsuppored mime {mime} for convert")
                mime = mimedetector.from_file(path)

            with open(path, "rb") as f:
                res = HttpResponse(f)
                if mime:
                    res["Content-type"] = mime
                res["Accept-Ranges"] = "bytes"
                return res
    raise HttpException404()


@login_required
def submit_diff(
    request: HttpRequest, login: str, assignment_id: int, submit_a: int, submit_b: int
) -> HttpResponse:
    submit = get_object_or_404(
        Submit, assignment_id=assignment_id, student__username=login, submit_num=submit_a
    )

    if not is_teacher(request.user) and request.user.username != submit.student.username:
        raise HttpException403()

    base_dir = os.path.dirname(submit.dir())
    dir_a = os.path.join(base_dir, str(submit_a))
    dir_b = os.path.join(base_dir, str(submit_b))

    files_a = os.listdir(dir_a)
    files_b = os.listdir(dir_b)

    excludes = []
    for root, subdirs, files in [*os.walk(dir_a), *os.walk(dir_b)]:
        for f in files:
            path = os.path.join(root, f)
            mime = mimedetector.from_file(path)
            if mime and not mime.startswith("image/") and not is_file_small(path):
                excludes.append("--exclude")

                p = os.path.relpath(path, base_dir).split("/")[1:]
                excludes.append(os.path.join(*p))

    def get_patch(p1, p2):
        # python3.7 does not support errors on TemporaryFile
        with tempfile.NamedTemporaryFile("r") as diff:
            subprocess.Popen(
                ["diff", "-ruiwN", *excludes] + [p1, p2], cwd=base_dir, stdout=diff
            ).wait()
            with open(diff.name, errors="ignore") as out:
                return out.read()

    # TODO: find better diffing tool that handles file renames
    if (
        len(files_a) == 1
        and os.path.isfile(files_a[0])
        and len(files_b) == 1
        and os.path.isfile(files_b[0])
    ):
        with tempfile.TemporaryDirectory() as p1, tempfile.TemporaryDirectory() as p2:
            with open(os.path.join(p1, "main.c"), "w") as out:
                with open(os.path.join(dir_a, files_a[0]), errors="ignore") as inp:
                    out.write(inp.read())
            with open(os.path.join(p2, "main.c"), "w") as out:
                with open(os.path.join(dir_b, files_b[0]), errors="ignore") as inp:
                    out.write(inp.read())

            out = get_patch(p1, p2)
            out = re.sub(r"^(---|\+\+\+) /tmp/[^/]+/", "\\1 ", out, flags=re.M)
    else:
        out = get_patch(str(submit_a), str(submit_b))
        out = re.sub(r"^(---|\+\+\+) [0-9]+/", "\\1 ", out, flags=re.M)

    out = "\n".join([line for line in out.split("\n") if not line.startswith("Binary file")])
    resp = HttpResponse(out)
    resp["Content-Type"] = "text/x-diff"
    return resp


def raw_test_content(request, task_name, test_name, file):
    task = get_object_or_404(Task, code=task_name)

    username = request.user.username
    if is_teacher(request.user) and "student" in request.GET:
        username = request.GET["student"]

    tests = create_taskset(task, username)

    for test in tests:
        if test.name == test_name:
            if file in test.files:
                return file_response(
                    test.files[file].open("rb"), f"{test_name}.{file}", "text/plain"
                )
    raise HttpException404()


def create_taskset(task: Task, user: str, meta: Optional[Dict[str, Any]] = None) -> TestSet:
    meta_dict = get_meta(user)

    if meta is not None:
        meta_dict.update(meta)
    task_dir = os.path.join(BASE_DIR, "tasks", task.code)
    return TestSet(task_dir, meta_dict)


def check_is_task_accessible(request: HttpRequest, task: Task):
    if not is_teacher(request.user):
        assigned_tasks = AssignedTask.objects.filter(
            task_id=task.pk, clazz__students__id=request.user.pk, assigned__lte=timezone.now()
        )
        if not assigned_tasks:
            raise HttpException403()


@login_required
def tar_test_data(request: HttpRequest, task_name: str) -> HttpResponse:
    def include_tests_script(tar, tests: TestSet):
        test_script = render_test_script(tests)
        info = tarfile.TarInfo("run-tests.py")
        info.size = len(test_script.getvalue())
        # Owner: rwx, group: rwx, other: r
        info.mode = 0o774

        tar.addfile(info, fileobj=test_script)

    task = get_object_or_404(Task, code=task_name)
    check_is_task_accessible(request, task)

    username = request.user.username
    if is_teacher(request.user) and "student" in request.GET:
        username = request.GET["student"]

    tests = create_taskset(task, username)

    with io.BytesIO() as f:
        with tarfile.open(fileobj=f, mode="w:gz") as tar:
            for test in tests:
                for file_path in test.files:
                    test_file = test.files[file_path]
                    info = tarfile.TarInfo(os.path.join(test.name, file_path))
                    info.size = test_file.size()
                    tar.addfile(info, fileobj=test_file.open("rb"))
            include_tests_script(tar, tests)

        f.seek(0)
        return file_response(f, f"{task_name}.tar.gz", "application/tar")


def zip_directory(directory: str) -> io.BytesIO:
    zip_buffer = io.BytesIO()

    src_path = Path(directory).expanduser().resolve(strict=True)
    with ZipFile(zip_buffer, "w", ZIP_DEFLATED) as zf:
        for file in src_path.rglob("*"):
            zf.write(file, file.relative_to(src_path.parent))
    return zip_buffer


@login_required
def task_asset(request: HttpRequest, task_name: str, path: str) -> HttpResponse:
    task = get_object_or_404(Task, code=task_name)
    try:
        check_is_task_accessible(request, task)
    except HttpException403:
        if not path.split("/")[-1].startswith("announce."):
            raise HttpException403()

    # Files and directories starting with . are private
    if any(p.startswith(".") for p in path.split("/")):
        raise HttpException403()

    deny_files = ["config.yml", "tests.yml", "script.py", "solution.c", "solution.cpp"]
    if (
        ".." in path
        or (path in deny_files and not is_teacher(request.user))
        or path.startswith("/")
    ):
        raise HttpException403()

    system_path = os.path.join("tasks", task_name, path)
    if request.method not in ["HEAD", "GET"]:
        if not is_teacher(request.user):
            raise HttpException403()

        if request.method == "PUT":
            os.makedirs(os.path.dirname(system_path), exist_ok=True)
            with open(system_path, "wb") as f:
                f.write(request.body)

            if path == "readme.md":
                readme = load_readme(task.code)
                # TODO What if readme is None?
                task.name = readme.name
                if not task.name:
                    task.name = task.code
                task.announce = True if readme.announce else False
                task.save()
            return HttpResponse(status=204)
        elif request.method == "DELETE":
            try:
                os.unlink(system_path)
            except FileNotFoundError:
                pass
            return HttpResponse(status=204)
        elif request.method == "MOVE":
            dst = request.headers["Destination"]
            if ".." in dst:
                raise HttpException403()
            system_dst = os.path.join("tasks", task_name, dst.lstrip("/"))
            if os.path.exists(system_path):
                os.makedirs(os.path.dirname(system_dst), exist_ok=True)
                shutil.move(system_path, system_dst)
                return HttpResponse(status=204)
            else:
                return HttpResponseNotFound()
        else:
            raise HttpException400()

    try:
        with open(system_path, "rb") as f:
            resp = HttpResponse(f)
            mime = mimedetector.from_file(system_path)
            if system_path.endswith(".js"):
                mime = "text/javascript"
            elif system_path.endswith(".wasm"):
                mime = "application/wasm"
            if mime:
                resp["Content-Type"] = f"{mime};charset=utf-8"
            return resp
    except FileNotFoundError:
        # Download directory as a .zip archive.
        # .tar.gz is also allowed as an extension to keep backwards compatibility
        archive_extensions = [".tar.gz", ".zip"]
        for archive_ext in archive_extensions:
            if system_path.endswith(archive_ext):
                directory = system_path[: -len(archive_ext)]
                if os.path.isdir(directory):
                    name = f"{os.path.basename(directory)}.zip"
                    f = zip_directory(directory)
                    f.seek(0)
                    return file_response(f, name, "application/x-zip")
        raise HttpException404()


# Files with these extensions will be opened in the browser directly
DIRECT_SHOW_EXTENSIONS = [".html", ".svg", ".png", ".jpg"]


@login_required
def raw_result_content(
    request: HttpRequest, submit_id: int, test_name: str, result_type: str, file: str
) -> HttpResponse:
    submit = get_object_or_404(Submit, pk=submit_id)

    if submit.student_id != request.user.pk and not is_teacher(request.user):
        raise HttpException403()

    submit_data: SubmitData = get_submit_data(submit)

    for pipe in submit_data.results:
        for test in pipe.tests:
            if test.name == test_name:
                if file in test.files:
                    if result_type in test.files[file]:
                        if result_type == "html":
                            return HttpResponse(
                                test.files[file][result_type].read(), content_type="text/html"
                            )
                        else:
                            file_content = test.files[file][result_type].open("rb").read()
                            file_name = f"{result_type}-{file}"
                            extension = os.path.splitext(file)[1]
                            file_mime = mimedetector.from_buffer(file_content)

                            if extension in DIRECT_SHOW_EXTENSIONS and file_mime:
                                return HttpResponse(file_content, content_type=file_mime)
                            return file_response(file_content, file_name, "text/plain")
    raise HttpException404()


def submit_download(
    request: HttpRequest, assignment_id: int, login: str, submit_num: int
) -> HttpResponse:
    submit = get_object_or_404(
        Submit, assignment_id=assignment_id, student__username=login, submit_num=submit_num
    )

    if "token" in request.GET:
        token = signing.loads(request.GET["token"], max_age=3600)
        if token.get("submit_id") != submit.id:
            raise HttpException403()
    elif not request.user.is_authenticated:
        return redirect(f"{settings.LOGIN_URL}?next={request.path}")
    elif not is_teacher(request.user) and request.user.username != submit.student.username:
        raise HttpException403()

    with io.BytesIO() as f:
        with tarfile.open(fileobj=f, mode="w:gz") as tar:
            for source in submit.all_sources():
                info = tarfile.TarInfo(source.virt)
                info.size = os.path.getsize(source.phys)
                info.mtime = os.path.getmtime(source.phys)
                with open(source.phys, "rb") as fr:
                    tar.addfile(info, fileobj=fr)

        f.seek(0)
        return file_response(f, f"{login}_{submit_num}.tar.gz", "application/tar")


@login_required
def ui(request: HttpRequest) -> HttpResponse:
    return render(request, "web/ui.html")


@csrf_exempt
def upload_results(
    request: HttpRequest, assignment_id: int, submit_num: int, login: str
) -> HttpResponse:
    submit = get_object_or_404(
        Submit, assignment_id=assignment_id, submit_num=submit_num, student__username=login
    )

    token = signing.loads(request.GET.get("token"), max_age=3600)
    if token.get("submit_id") != submit.id:
        raise HttpException403()

    result_path = os.path.join(
        "submit_results",
        *submit.path_parts(),
    )

    with tarfile.open(fileobj=io.BytesIO(request.body)) as tar:
        tar.extractall(result_path)

    submit_data: SubmitData = get_submit_data(submit)

    for pipe in submit_data.results.pipelines:
        if "points" in pipe:
            overwrite = "points_overwrite" in pipe and pipe.points_overwrite
            if (submit.assigned_points is not None and overwrite) or submit.assigned_points is None:
                submit.assigned_points = pipe.points
                submit.save()

    return JsonResponse({"success": True})


@login_required()
def mark_solution_as_final(
    request: HttpRequest, assignment_id: int, login: str, submit_num: int
) -> HttpResponse:
    submit = get_object_or_404(
        Submit, assignment_id=assignment_id, submit_num=submit_num, student__username=login
    )

    user_is_teacher = is_teacher(request.user)

    if not user_is_teacher and submit.created_at > submit.assignment.deadline:
        raise HttpException400("Attempting to mark a submit after deadline.")

    if not user_is_teacher and login != request.user.username:
        raise HttpException403()

    last_submit = (
        Submit.objects.filter(assignment__pk=assignment_id, student__username=login)
        .order_by("-created_at")
        .first()
    )

    if last_submit is None or submit.pk == last_submit.pk:
        submit.is_final = True

        submit.save()

        assignment = get_object_or_404(AssignedTask, id=assignment_id)
        record_final_submit_event(request, request.user, task=assignment, submit_num=submit_num)

        return redirect("task_detail", assignment_id, login, submit_num)
    else:
        raise HttpException400(
            "Attempting to mark a submit which is not the most recently submitted one as final."
        )


@user_passes_test(is_teacher)
def unmark_solution_final_mark(
    request: HttpRequest, assignment_id: int, login: str, submit_num: int
) -> HttpResponse:
    submit = get_object_or_404(
        Submit, assignment_id=assignment_id, submit_num=submit_num, student__username=login
    )

    submit.is_final = False

    submit.save()

    return redirect("task_detail", assignment_id, login, submit_num)


def teacher_task_tar(request: HttpRequest, task_id: int) -> FileResponse:
    task = get_object_or_404(Task, id=task_id)

    if "token" in request.GET:
        token = signing.loads(request.GET["token"], max_age=3600)
        if token.get("task_id") != task_id:
            raise HttpException403()
    elif not is_teacher(request.user):
        raise HttpException403()

    f = tempfile.TemporaryFile()
    with tarfile.open(fileobj=f, mode="w") as tar:
        tar.add(task.dir(), "")
    f.seek(0, io.SEEK_SET)

    res = FileResponse(f)
    res["Content-Type"] = "application/x-tar"
    return res


@login_required
def quiz_fill(request: HttpRequest) -> HttpResponse | HttpResponseRedirect:
    """
    Function that allows filling a quiz.
    """
    if request.method != "GET":
        raise HttpException400()

    try:
        enrolled_quiz = EnrolledQuiz.objects.get(student=request.user.pk, submitted=False)

        now = timezone.now()

        # If enrolled quiz is after deadline and still not submitted, it's marked as submitted
        if now > enrolled_quiz.deadline:
            enrolled_quiz.submitted = True
            enrolled_quiz.submitted_at = now
            score_quiz(enrolled_quiz)

        # If enrolled quiz is submitted, it redirects to the results page if and only if results are allowed to be published,
        # otherwise redirects to main page.
        if enrolled_quiz.submitted:
            if enrolled_quiz.assigned_quiz.publish_results:
                return HttpResponseRedirect(reverse("quiz_result", args=[enrolled_quiz.pk]))
            else:
                return HttpResponseRedirect("/")

        # Student will continue solving active quiz.
        remaining = enrolled_quiz.deadline - now

        data = dict(
            is_teacher=is_teacher(request.user),
            quiz_id=enrolled_quiz.assigned_quiz.quiz.pk,
            enrolled_id=enrolled_quiz.pk,
            remaining=remaining.total_seconds(),
            scoring=None,
            student=None,
            answers=json.dumps(enrolled_quiz.submit),
            quiz_html=json.dumps(
                quiz_to_html(enrolled_quiz.assigned_quiz.quiz.src, enrolled_quiz.template.content)
            ),
        )

        return render(request, "web/quiz/quiz.html", dict(data=data))

    except EnrolledQuiz.DoesNotExist:  # no active quiz
        return HttpResponseRedirect("/")


@login_required
def quiz_enrolling(request: HttpRequest, assignment_id: int) -> HttpResponse:
    """
    Function that renders informative enrolling page.
    """
    assigned_quiz = get_object_or_404(AssignedQuiz, pk=assignment_id)

    now = timezone.now()

    # If student is not member of a class, or quiz is not able to be enrolled yet, it redirects to the main page.
    if (
        assigned_quiz.clazz.students.filter(username=request.user.username).count() == 0
        or assigned_quiz.assigned > now
    ):
        return HttpResponseRedirect("/")

    return render(
        request,
        "web/quiz/quiz_enrolling.html",
        {"assignment": assigned_quiz, "quiz": assigned_quiz.quiz},
    )


@login_required
def quiz_result(request: HttpRequest, enrolled_id: int) -> HttpResponse | HttpResponseRedirect:
    """
    Function that renders the results of a quiz for student if possible, otherwise redirects to main page, or returns 404
    if enroll for quiz not exists.
    """
    enrolled_quiz = get_object_or_404(EnrolledQuiz, pk=enrolled_id)

    if (
        request.user != enrolled_quiz.student
        or not enrolled_quiz.submitted
        or not enrolled_quiz.assigned_quiz.publish_results
    ):
        return HttpResponseRedirect("/")

    scored_by = "System Kelvin"

    if enrolled_quiz.scored_by is not None:
        scored_by = enrolled_quiz.scored_by.username

    data = dict(
        is_teacher=is_teacher(request.user),
        quiz_id=enrolled_quiz.assigned_quiz.quiz.pk,
        enrolled_id=enrolled_quiz.pk,
        scoring=json.dumps(enrolled_quiz.scoring),
        answers=json.dumps(enrolled_quiz.submit),
        student=None,
        scored_by=scored_by,
        quiz_html=json.dumps(
            quiz_to_html(enrolled_quiz.assigned_quiz.quiz.src, enrolled_quiz.template.content)
        ),
    )

    return render(request, "web/quiz/quiz.html", dict(data=data))


@login_required
def quiz_asset(request: HttpRequest, quiz_src: str, asset_path: str) -> HttpResponse:
    """
    Function that returns an asset of a quiz folder if asset is found, 404 otherwise.
    Raises permission denied if user is trying to access something he can't.
    """
    path = quiz_src + asset_path

    teacher_user = is_teacher(request.user)

    if ".." in path or ("quiz.yml" in path and not teacher_user):
        raise HttpException403()

    system_path = os.path.join(QUIZ_PATH, quiz_src, asset_path)

    if not Path(system_path).is_relative_to(QUIZ_PATH):
        raise HttpException403()

    if not teacher_user:
        try:
            with open(os.path.join(QUIZ_PATH, quiz_src, ".quiz_id")) as f:
                quiz_id = int(f.read())
        except FileNotFoundError:
            raise HttpException404()

        has_access = request.user.enrolledquiz_set.filter(assigned_quiz__quiz__id=quiz_id).exists()

        if not has_access:
            raise HttpException403()

    try:
        with open(system_path, "rb") as f:
            resp = HttpResponse(f)
            mime = mimedetector.from_file(system_path)
            if mime:
                resp["Content-Type"] = f"{mime};charset=utf-8"
            return resp
    except FileNotFoundError:
        raise HttpException404()
