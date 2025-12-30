from functools import wraps

from django.core import signing
from django.shortcuts import get_object_or_404
from ninja.errors import HttpError
from typing_extensions import Protocol

from common.models import Submit
from common.utils import is_teacher


class RequireAuthTokenProtocol(Protocol):
    def __call__(self, request, *args, **kwargs): ...


class RequireSubmitProtocol(Protocol):
    def __call__(self, request, submit_id: int, *args, **kwargs): ...


def require_auth_token(function: RequireAuthTokenProtocol):
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


def require_submit_access_by_token(function: RequireSubmitProtocol):
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


def get_submit_write_access(request, assignment_id: int, login: str, submit_num: int) -> Submit:
    """
    Fetch the Submit instance and ensure the requesting user has write access.

    Behavior:
        - Fetches the Submit instance based on assignment_id, login, and submit_num
        - Checks if the user is a teacher or the owner of the submission
        - Returns the Submit instance if access is granted
        - On failure, raises HttpError(403)
    """
    submit_instance: Submit = get_object_or_404(
        Submit, assignment_id=assignment_id, student__username=login, submit_num=submit_num
    )

    is_teacher_role: bool = is_teacher(request.user)
    is_submit_owner: bool = request.user.username == submit_instance.student.username

    if not is_teacher_role and not is_submit_owner:
        raise HttpError(403, "You do not have permission to modify this submission.")

    return submit_instance
