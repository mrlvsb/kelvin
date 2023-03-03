import logging
import mimetypes

import django_rq
import rq
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import caches
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import cache_page
from django.views.decorators.clickjacking import xframe_options_sameorigin
from notifications.models import Notification

from common.models import Submit, Task, current_semester
from common.moss import PlagiarismMatch, enqueue_moss_check, get_match_local_dir, \
    moss_delete_job_from_cache, \
    moss_job_cache_key, \
    moss_result, moss_task_get_opts, moss_task_set_opts
from common.moss.local_result import download_moss_result
from common.utils import is_teacher
from web.views.teacher import enrich_matches
from web.views.utils import file_response


@user_passes_test(is_teacher)
def task_moss_check(request, task_id):
    # clear MOSS notifications
    Notification.objects.filter(
        action_object_object_id=task_id,
        recipient_id=request.user.id,
        verb="plagiarism",
    ).update(unread=False)

    cache = caches['default']
    key_job = moss_job_cache_key(task_id)

    task = get_object_or_404(Task, pk=task_id)

    job_id = cache.get(key_job)
    if job_id:
        refresh = False
        try:
            job = django_rq.jobs.get_job_class().fetch(job_id,
                                                       connection=django_rq.queues.get_connection())
            status = job.get_status()
            if status == "started":
                refresh = True
            elif status == "queued":
                refresh = True
                status += f" {job.get_position() + 1}"
            elif status == "failed" and job.exc_info:
                status += f"\n{job.exc_info}"
                moss_delete_job_from_cache(task_id)
        except (rq.exceptions.NoSuchJobError, AttributeError) as e:
            moss_delete_job_from_cache(task_id)
            logging.exception(e)
            status = "unknown"
        return render(request, "web/moss.html", {
            "status": status,
            "task": task,
            "refresh": refresh
        })

    if request.method == 'POST':
        enqueue_moss_check(task_id)
        return redirect(request.path_info)

    opts = moss_task_get_opts(task_id)

    if 'percent' in request.GET:
        opts = {
            **opts,
            "percent": int(request.GET.get("percent", 5)),
            "lines": int(request.GET.get("lines", 1)),
            "show_to_students": int(request.GET.get("show_to_students", False)),
        }
        moss_task_set_opts(task_id, opts)

    res = moss_result(task_id, percent=opts['percent'], lines=opts['lines'])
    if not res:
        return render(request, 'web/moss.html', {
            "task": task,
            "has_result": False
        })
    else:
        newer_submit_count = Submit.objects.filter(
            assignment__task_id=task.id,
            created_at__gt=res.started_at
        ).count()
        matches = enrich_matches(res.matches, request.user, task)
        return render(request, "web/moss.html", {
            "has_result": True,
            "success": res.success,
            "log": res.log,
            "matches": matches,
            "graph": res.to_svg(anonymize=False),
            "opts": res.opts,
            "started_at": res.started_at,
            "finished_at": res.finished_at,
            "moss_url": res.url,
            "newer_submit_count": newer_submit_count,
            "task": task,
            "semester": str(current_semester())
        })


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
    Returns a HTML (or other resource) content of a MOSS result.
    If the result is not available locally, it is first fetched from MOSS and cached in a
    directory belonging to the task.

    Only teachers and students that were matched in the specified `match_id` can view this content.
    """
    task = get_object_or_404(Task, pk=task_id)
    res = moss_result(task_id)
    if res is None or not (0 <= match_id < len(res.matches)):
        raise Http404
    match: PlagiarismMatch = res.matches[match_id]

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
