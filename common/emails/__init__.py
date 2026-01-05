import datetime
import logging
import traceback
from typing import Callable, TYPE_CHECKING

from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import transaction
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse

from .models import Email

if TYPE_CHECKING:
    from common.models import Submit


def send_email_points_assigned(
    request: HttpRequest, sender: User, student: User, submit: "Submit", points: float
):
    content = render_to_string(
        "emails/points-assigned.html",
        context=dict(
            teacher=sender,
            student=student,
            submit=submit,
            points=format_points(points),
            max_points=submit.assignment.max_points,
            url=request.build_absolute_uri(
                reverse(
                    "task_detail",
                    kwargs=dict(assignment_id=submit.assignment.pk, login=student.username),
                )
            ),
        ),
    )

    Email.create(subject="Obodování úlohy / solution scored", text=content, receiver=student)


logger = logging.getLogger(__name__)


def with_email_to_send(handle_email: Callable[[Email], None]):
    """
    Tries to pop a single e-mail from the database and pass it to the closure.
    If the closure doesn't raise an exception, we assume that sending of the e-mail succeeded,
    and the e-mail will be marked as sent in the database.
    If an exception is thrown, the e-mail will not be marked as sent.

    If there is no e-mail to send, the closure will not be called.

    Also ensures that we do not send an e-mail too often.
    """

    # Make sure that we do not send an e-mail more often than once every ten seconds
    # This can be relevant especially when Kelvin is being restarted and multiple jobs have been
    # queued up.
    last_sent_email = Email.objects.filter(sent_at__isnull=False).order_by("-sent_at").first()
    now = datetime.datetime.now(datetime.UTC)
    if last_sent_email is not None and (now - last_sent_email.sent_at) < datetime.timedelta(
        seconds=10
    ):
        logger.warning(
            f"Trying to send e-mail too often. Last e-mail sent at {last_sent_email.sent_at}"
        )
        return

    with transaction.atomic(durable=True):
        email = (
            Email.objects.filter(sent_at__isnull=True, attempt_count__lte=5)
            .order_by("created_at")
            # Ensure that we lock the selected row when handling the e-mail, and skip already
            # skipped rows.
            .select_for_update(skip_locked=True)
            .first()
        )
        if email:
            # We want to increment the attempt count even if the handling fails
            # Note that if the app crashes in the middle of the transaction, the increment could
            # be lost, but that shouldn't be such a big problem.
            # An alternative design would be to always increment the attempt count and then use
            # some timeout in the table to avoid performing the e-mail send itself within the
            # transaction.
            email.attempt_count += 1
            try:
                logger.info(f"Trying to send e-mail to {email.receiver.email}")
                handle_email(email)
                # The function did not throw an exception, so mark the email as sent
                email.sent_at = datetime.datetime.now(datetime.UTC)
                logger.info("E-mail successfully sent")
            except BaseException as e:
                logger.error("Failure while sending e-mail\n{}", traceback.format_exception(e))
            email.save()


def try_send_email_from_queue():
    """
    Tries to pop a single (not yet sent) e-mail from the DB and send it.
    """

    def send(email: Email):
        logger.info(f"Sending an e-mail with subject `{email.subject}` to `{email.receiver.email}`")
        send_mail(
            f"[Kelvin] {email.subject}",
            message=email.text,
            from_email=settings.DEFAULT_FROM_EMAIL,
            # recipient_list=[email.receiver.email],
            # Temporarily send here for testing
            recipient_list=["jakub.beranek@vsb.cz"],
            fail_silently=False,
        )

    with_email_to_send(send)


def format_points(points: float) -> str:
    """Formats points so that they are rendered as an integer if they do not
    have a decimal part."""
    return f"{points:.2f}".rstrip("0").rstrip(".")
