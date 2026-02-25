import logging

from django.http import HttpRequest

from common.exceptions import HttpExceptionData
from kelvin import settings
from web.views.common import render_custom_error_page

logger = logging.getLogger(__name__)

"""
Having custom error pages in Django is.. stupidly hard.

We want to render a custom error page when:
1) DEBUG is not enabled (we are in production)
2) The request was not for the /api module (which uses JSON requests/responses)

Ideally, we could find when a HTTP response with a non-OK status code is returned,
and render a custom error page when that happens.

However, Django:
1) Handles certain exceptions (400, 403 and 404) on its own, and renders a custom page when they
happen. To avoid distinguishing between Django's and our usage of those exceptions, and
double-wrapping the already rendered view in our custom error page again, we do not do anything with
HTML responses. Instead, we use the handler400/403/404 variables in `urls.py` to let Django use our
error page template when these exceptions happen.
2) Allows us to catch exceptions with middleware (`process_exception`), but not for everything :(
Some exceptions (such as a path not being found) are **special**, and are handled immediately with
the 404 view handler. So we have to use the custom handlers, rather than dealing with everything
inside middleware.

In short, it's quite hard to achieve both:
1) Returning HTTP responses with a non-OK status code
2) Rendering them with a custom error page

So instead, we create our own exceptions, and raise exceptions when wanting to return non-OK
response content.
"""


class KelvinExceptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        return self.get_response(request)

    def process_exception(self, request, exception):
        if should_exception_be_handled(request):
            # Log the error ourselves, otherwise Django would not add a stacktrace
            if HttpExceptionData.from_exception(exception).status >= 500:
                logger.error(
                    "Internal Server Error: %s",
                    request.path,
                    exc_info=True,
                    extra={"status_code": 500, "request": request},
                )
            response = render_custom_error_page(request, exception=exception)
            # Prevent Django's get_response from calling log_response again without exc_info,
            # which would send a duplicate email without a stacktrace.
            response._has_been_logged = True
            return response
        return None


def should_exception_be_handled(request: HttpRequest) -> bool:
    """
    Returns true if we should render a custom error page for a failed response
    for the given request.
    """
    # Use the default Django error reporting in DEBUG mode
    if settings.DEBUG:
        return False

    # API requests should not get a custom error page
    return not request.path.startswith("/api/")
