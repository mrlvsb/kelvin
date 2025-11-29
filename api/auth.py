from functools import wraps

from django.core import signing
from django.shortcuts import get_object_or_404
from ninja.errors import HttpError

from common.models import Submit
from common.utils import is_teacher


def require_auth_token(function):
    """
    Validate a signed token passed through the query string.

    Behavior:
        - Reads "token" from request.GET
        - Validates the token signature and age (max_age = 3600 seconds)
        - On failure, raises HttpError(403)

    This decorator is suitable for routes that require authenticated access via
    signed tokens.
    """

    @wraps(function)
    def wrapper(request, *args, **kwargs):
        token_value = request.GET.get("token")
        if token_value is None:
            raise HttpError(403, "Token missing")

        try:
            signing.loads(token_value, max_age=3600)
        except Exception:
            raise HttpError(403, "Invalid or expired token")

        return function(request, *args, **kwargs)

    return wrapper


def require_submit_access_by_token(function):
    """
    Validate a signed token passed through the query string and ensure it belongs
    to the same submit_id as the current request.

    Behavior:
        - Reads "token" from request.GET
        - Validates the token signature and age (max_age = 3600 seconds)
        - Ensures the token contains a "submit_id" matching the request's submit_id
        - On failure, raises HttpError(403)

    This decorator keeps endpoint logic clean by centralizing verification of
    submit-specific tokens for routes that accept a submit_id path parameter.
    """

    @wraps(function)
    def wrapper(request, submit_id: int, *args, **kwargs):
        token_value = request.GET.get("token")
        if token_value is None:
            raise HttpError(403, "Token missing")

        try:
            decoded_token = signing.loads(token_value, max_age=3600)
        except Exception:
            raise HttpError(403, "Invalid or expired token")

        submit_from_token = decoded_token.get("submit_id")
        if submit_from_token != submit_id:
            raise HttpError(403, "Permission denied, submit_id mismatch")

        return function(request, submit_id, *args, **kwargs)

    return wrapper


def require_submit_access(function):
    """
    Ensure the requesting user has access to the specified submission.

    Behavior:
        - Fetches the Submit instance based on assignment_id, login, and submit_num
        - Checks if the user is a teacher or the owner of the submission
        - Attaches the Submit instance to request.submit_instance for downstream use
        - On failure, raises HttpError(403)
    """

    @wraps(function)
    def wrapper(request, assignment_id: int, login: str, submit_num: int, *args, **kwargs):
        submit_instance: Submit = get_object_or_404(
            Submit, assignment_id=assignment_id, student__username=login, submit_num=submit_num
        )

        # Attaching the submit instance to the request for downstream use, this way
        # we avoid fetching it again in the decorated function.
        request.submit_instance = submit_instance

        is_teacher_role: bool = is_teacher(request.user)
        is_submit_owner: bool = request.user.username == submit_instance.student.username

        if not is_teacher_role and not is_submit_owner:
            raise HttpError(403, "You do not have permission to access this submission.")

        return function(request, assignment_id, login, submit_num, *args, **kwargs)

    return wraps(function)(wrapper)
