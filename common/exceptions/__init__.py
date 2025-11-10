import dataclasses

from django.core.exceptions import BadRequest, PermissionDenied, RequestDataTooBig, TooManyFilesSent
from django.http import Http404
from django.urls import Resolver404

from common.exceptions.http_exceptions import HttpException


@dataclasses.dataclass
class HttpExceptionData:
    status: int
    message: str

    @staticmethod
    def from_exception(exception) -> "HttpExceptionData":
        status = 500
        message = "Server error"

        match exception:
            case RequestDataTooBig():
                status, message = (400, "Too much data uploaded")
            case TooManyFilesSent():
                status, message = (400, "Too many files sent")
            case BadRequest():
                status, message = (400, str(exception))
            case PermissionDenied():
                status, message = (403, str(exception))
            case Resolver404():
                status, message = (404, "Path not found")
            case Http404():
                status, message = (404, str(exception))
            case HttpException():
                status, message = (exception.code, exception.message)
        return HttpExceptionData(status=status, message=message)
