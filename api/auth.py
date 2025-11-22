from functools import wraps

from django.core import signing
from ninja.errors import HttpError


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


def require_submit_token(function):
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
