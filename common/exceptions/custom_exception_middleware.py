# middleware.py

from django.shortcuts import render

from common.exceptions.exception_parser import parse_exception


class CustomExceptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    @staticmethod
    def process_exception(request, e):
        exception = parse_exception(request, e)

        if exception is not None:
            return render(request, "error_page.html", exception)

        return None
