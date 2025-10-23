import datetime

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import BadRequest
from django.http import HttpRequest
from notifications.models import Notification
from notifications.signals import notify

from common.evaluate import evaluate_submit
from common.event_log import record_submit_event
from common.models import AssignedTask, Submit
from common.upload import upload_submit_files
from common.utils import is_teacher, get_client_ip_address

# How much time has to be elapsed between two consecutive submits.
# Note that this is not perfect due to us not using atomicity properly, but it's
# better than nothing.
SUBMIT_RATELIMIT = datetime.timedelta(seconds=30)


class SubmitRateLimited(Exception):
    def __init__(self, message: str, time_until_limit_expires: datetime.timedelta):
        super().__init__(message)

        self.time_until_limit_expires = time_until_limit_expires


class SubmitPastHardDeadline(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class SubmitAfterFinal(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class SubmitFromUnauthorizedIPError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


def store_submit(request: HttpRequest, assignment: AssignedTask) -> Submit:
    """
    Creates a new submit for the given `assignment` and the user logged in the `request`.
    Expects that the POST request contains a multipart form with a (potentially repeated)
    "solution" field that contains uploaded files.
    Optionally, the request can also contain a "paths" field that contains a string with a single
    path per line, assigning paths to the uploaded "solution" files.
    """
    if (
        assignment.has_hard_deadline()
        and assignment.is_past_deadline()
        and not is_teacher(request.user)
    ):
        raise SubmitPastHardDeadline("Submit was submitted after deadline")

    # Get existing submits of the student
    submits = list(
        Submit.objects.filter(assignment__pk=assignment.id, student__pk=request.user.id).order_by(
            "-created_at"
        )
    )

    # Check submit date across all tasks, just to be a bit more defensive
    last_student_submit = (
        Submit.objects.filter(student=request.user).order_by("-created_at").first()
    )

    if last_student_submit is not None:
        since_last_submit = (
            datetime.datetime.now(datetime.timezone.utc) - last_student_submit.created_at
        )
        if since_last_submit < SUBMIT_RATELIMIT:
            raise SubmitRateLimited("Submit was rate limited", SUBMIT_RATELIMIT - since_last_submit)

    if any(s.is_final for s in submits):
        raise SubmitAfterFinal("Attempt to create submit after marking previous as final")

    # TODO: transaction/better submit_num checking
    s = Submit()
    s.student = request.user
    s.assignment = assignment
    s.submit_num = len(submits) + 1
    client_ip = get_client_ip_address(request)
    if client_ip:
        s.ip_address = client_ip

    if assignment.allowed_classrooms:
        if not assignment.is_allowed_from_ip(client_ip):
            raise SubmitFromUnauthorizedIPError(
                "It is forbidden to upload solutions from this IP address"
            )

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

    record_submit_event(
        request=request, user=request.user, task=assignment, submit_num=s.submit_num
    )

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
