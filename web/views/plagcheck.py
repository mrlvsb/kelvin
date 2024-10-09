import dataclasses
import logging
import mimetypes
from pathlib import Path
from typing import List

import django_rq
import rq
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import caches
from django.http import (
    Http404,
    HttpResponse,
    HttpRequest,
    HttpResponseNotFound,
    FileResponse,
    HttpResponseBadRequest,
    HttpResponseBase,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import cache_page
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_http_methods
from django.views.static import serve
from notifications.models import Notification

from common.models import Semester, Submit, Task, current_semester
from common.plagcheck.dolos import (
    get_dolos_log_path,
    get_dolos_result,
    DolosResultMissing,
    DolosResultFailed,
    DolosResultPresent,
)
from common.plagcheck.moss import (
    PlagiarismMatch,
    get_match_local_dir,
    moss_delete_job_from_cache,
    moss_job_cache_key,
    moss_result,
    moss_task_get_opts,
    moss_task_set_opts,
)
from common.plagcheck import get_linked_tasks, enqueue_plagiarism_check
from common.plagcheck.moss.local_result import download_moss_result
from common.utils import is_teacher
from kelvin.settings import BASE_DIR
from web.views.teacher import enrich_matches
from web.views.utils import file_response


@dataclasses.dataclass
class LinkedTask:
    id: int
    name: str
    semesters: str


def get_linked_task_data(task_id: int) -> List[LinkedTask]:
    tasks = get_linked_tasks(task_id)
    linked_tasks = []
    for task in tasks:
        semesters = (
            Semester.objects.filter(pk__in=task.assignedtask_set.values("clazz__semester"))
            .distinct()
            .all()
        )
        semesters = ", ".join(
            str(s) for s in sorted(semesters, key=lambda s: (s.year, 0 if s.winter else 1))
        )
        linked_tasks.append(LinkedTask(id=task.id, name=task.name, semesters=semesters))

    return linked_tasks


@user_passes_test(is_teacher)
def task_plagcheck_index(request: HttpRequest, task_id: int):
    # Clear plagcheck notifications
    Notification.objects.filter(
        action_object_object_id=task_id,
        recipient_id=request.user.id,
        verb="plagiarism",
    ).update(unread=False)

    cache = caches["default"]
    key_job = moss_job_cache_key(task_id)

    task = get_object_or_404(Task, pk=task_id)
    linked_tasks = get_linked_task_data(task_id)

    # Configure task options
    opts = moss_task_get_opts(task_id)
    if "percent" in request.GET:
        opts.percent = int(request.GET["percent"])
        opts.lines = int(request.GET.get("lines", opts.lines))
        moss_task_set_opts(task_id, opts)

    ctx = {
        "task": task,
        "linked_tasks": linked_tasks,
        "semester": str(current_semester()),
        "opts": opts,
    }

    dolos_result = get_dolos_result(task)
    if not isinstance(dolos_result, DolosResultMissing):
        ctx["dolos_url"] = reverse(
            "teacher_task_dolos_page", kwargs=dict(task_id=task_id, path="/")
        )

    status = "missing"
    metadata = ""

    job_id = cache.get(key_job)
    if job_id:
        """
        In this case, the plagiarism check has been schedule and is running (or waiting to run).
        """
        try:
            job = django_rq.jobs.get_job_class().fetch(
                job_id, connection=django_rq.queues.get_connection()
            )
            status = job.get_status()
            if status == "queued":
                metadata = f"Position in queue: {job.get_position() + 1}"
            elif status == "failed" and job.exc_info:
                metadata = job.exc_info
                moss_delete_job_from_cache(task_id)
        except (rq.exceptions.NoSuchJobError, AttributeError) as e:
            status = "failed"
            metadata = str(e)
            moss_delete_job_from_cache(task_id)
            logging.exception(e)

    ctx["refresh"] = status in ("started", "queued")
    ctx["metadata"] = metadata

    res = moss_result(task_id, percent=opts.percent, lines=opts.lines)
    if res:
        status = "present"
        newer_submit_count = Submit.objects.filter(
            assignment__task_id=task.id, created_at__gt=res.started_at
        ).count()
        matches = enrich_matches(res.matches, request.user, task)
        if not res.success:
            status = "failed"
        ctx["log"] = res.log
        ctx["matches"] = matches
        ctx["graph"] = res.to_svg(anonymize=False)
        ctx["started_at"] = res.started_at
        ctx["finished_at"] = res.finished_at
        ctx["moss_url"] = res.url
        ctx["newer_submit_count"] = newer_submit_count
    ctx["status"] = status
    return render(
        request,
        "web/plagcheck.html",
        ctx,
    )


@user_passes_test(is_teacher)
@require_http_methods(["POST"])
def task_plagcheck_start(request: HttpRequest, task_id: int):
    submit_limit = request.POST.get("submit-limit")
    submit_limit = None if not submit_limit else int(submit_limit)
    enqueue_plagiarism_check(task_id, submit_limit=submit_limit)
    return redirect(reverse("teacher_task_plagiarism", kwargs=dict(task_id=task_id)))


@user_passes_test(is_teacher)
def task_moss_graph(request, task_id):
    res = moss_result(task_id)
    if res is None:
        raise Http404
    task = get_object_or_404(Task, pk=task_id)
    graph = res.to_svg(anonymize=True)
    return file_response(graph.encode("utf8"), f"{task.name}-graph.svg", "image/svg+xml")


@login_required
@xframe_options_sameorigin
@cache_page(60 * 60)
def task_moss_result(request, task_id: int, match_id: int, path: str):
    """
    Returns an HTML (or other resource) content of a MOSS result.
    If the result is not available locally, it is first fetched from MOSS and cached in a
    directory belonging to the task.

    Only teachers and students that were matched in the specified `match_id` can view this content.
    """
    task = get_object_or_404(Task, pk=task_id)
    res = moss_result(task_id, filtered=False)
    if res is None:
        raise Http404

    found_matches = [match for match in res.matches if match.id == match_id]
    if len(found_matches) != 1:
        raise Http404
    match: PlagiarismMatch = found_matches[0]

    user_is_teacher = is_teacher(request.user)
    if not user_is_teacher and request.user.username not in (match.first.login, match.second.login):
        raise Http404

    refresh_requested = request.GET.get("refresh") is not None and user_is_teacher

    match_dir = get_match_local_dir(task, match)
    if not match_dir.is_dir() or refresh_requested:
        download_moss_result(match.moss_link, match_dir)

    local_path = match_dir / path
    if local_path.parent != match_dir:
        raise Http404

    mimetype = mimetypes.guess_type(local_path)[0]
    return HttpResponse(open(match_dir / path, "rb"), mimetype)


@user_passes_test(is_teacher)
def dolos_page(request: HttpRequest, path: str, task_id: int) -> HttpResponse:
    """
    Return the Dolos SPA web.
    """
    task = get_object_or_404(Task, pk=task_id)
    result = get_dolos_result(task)
    if isinstance(result, DolosResultMissing):
        return HttpResponseNotFound()
    elif isinstance(result, DolosResultFailed):
        # The check has failed, redirect the user to the log
        return redirect(reverse("teacher_task_dolos_log", kwargs=dict(task_id=task_id)))
    elif isinstance(result, DolosResultPresent):
        return serve_static_dolos(request, path)
    else:
        assert False


@user_passes_test(is_teacher)
def dolos_result_log(request: HttpRequest, task_id: int) -> HttpResponse:
    """
    Returns the log of a dolos check.
    """
    task = get_object_or_404(Task, pk=task_id)
    result = get_dolos_result(task)
    if isinstance(result, DolosResultMissing):
        return HttpResponseNotFound()
    with open(get_dolos_log_path(task)) as f:
        return HttpResponse(f"<pre>{f.read()}</pre>")


def serve_static_dolos(request: HttpRequest, path: str) -> HttpResponse:
    """
    Serve the Dolos SPA from web/static/dolos.
    """
    path = path.lstrip("/")
    if path == "":
        path = "index.html"

    return serve(request, path, document_root=Path(BASE_DIR) / "web" / "static" / "dolos")


@user_passes_test(is_teacher)
def dolos_result(request: HttpRequest, task_id: int, path: str) -> HttpResponseBase:
    """
    Return a dynamic Dolos CSV result file.
    """
    task = get_object_or_404(Task, pk=task_id)
    result = get_dolos_result(task)
    if isinstance(result, DolosResultMissing) or isinstance(result, DolosResultFailed):
        return HttpResponseNotFound()
    elif isinstance(result, DolosResultPresent):
        file = result.dir / path
        if not file.is_relative_to(result.dir):
            return HttpResponseBadRequest()
        if file.is_file() and file.suffix == ".csv":
            return FileResponse(open(file, "rb"), filename=file.name, content_type="text/csv")
    else:
        assert False
