import hashlib

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import BadRequest
from django.http import HttpRequest
from notifications.models import Notification
from notifications.signals import notify

from common.evaluate import evaluate_submit
from common.models import AssignedTask, Submit
from common.upload import upload_submit_files
from common.utils import is_teacher


def store_submit(request: HttpRequest, assignment: AssignedTask) -> Submit:
    """
    Creates a new submit for the given `assignment` and the user logged in the `request`.
    Expects that the POST request contains a multipart form with a (potentially repeated)
    "solution" field that contains uploaded files.
    Optionally, the request can also contain a "paths" field that contains a string with a single
    path per line, assigning paths to the uploaded "solution" files.
    """
    def get_request_ip(request):
        # TODO: refactor this
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            x_forwarded_for = x_forwarded_for.split(",")[0].strip()
        return x_forwarded_for

    submits = Submit.objects.filter(
        assignment__pk=assignment.id,
    ).order_by("-id")

    # TODO: transaction/better submit_num checking
    s = Submit()
    s.student = request.user
    s.assignment = assignment
    s.submit_num = (
        Submit.objects.filter(assignment__id=s.assignment.id, student__id=request.user.id).count()
        + 1
    )
    s.ip_address_hash = get_request_ip(request)
    if s.ip_address_hash:
        s.ip_address_hash = hashlib.sha256(s.ip_address_hash.encode()).hexdigest()

    solutions = request.FILES.getlist("solution")
    tmp = request.POST.get("paths", None)
    if tmp:
        paths = [f.rstrip("\r") for f in tmp.split("\n") if f.rstrip("\r")]
    else:
        paths = [f.name for f in solutions]

    if solutions is None or len(solutions) != len(paths) or len(solutions) == 0:
        raise BadRequest("No files were uploaded")

    upload_submit_files(s, paths, solutions)

    # we need submit_id before putting the job to the queue
    s.save()
    s.jobid = evaluate_submit(request, s).id
    s.save()

    # delete previous notifications
    Notification.objects.filter(
        action_object_object_id__in=[str(s.id) for s in submits],
        action_object_content_type=ContentType.objects.get_for_model(Submit),
        verb="submitted",
    ).delete()

    if not is_teacher(request.user):
        notify.send(
            sender=request.user,
            recipient=[assignment.clazz.teacher],
            verb="submitted",
            action_object=s,
            important=any([s.assigned_points is not None for s in submits]),
        )
    return s
