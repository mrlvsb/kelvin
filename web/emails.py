from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse

from common.models import Submit


def send_email_points_assigned(
    request: HttpRequest, sender: User, student: User, submit: Submit, points: float
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

    # TODO: use an e-mail queue and add debouncing to avoid spam
    send_mail(
        "[Kelvin] Obodování úlohy / solution scored",
        content,
        "kelvin@vsb.cz",
        [student.email],
        fail_silently=True,
    )


def format_points(points: float) -> str:
    """Formats points so that they are rendered as an integer if they do not
    have a decimal part."""
    return f"{points:.2f}".rstrip("0").rstrip(".")
