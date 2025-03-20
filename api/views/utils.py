from django.http import JsonResponse


def MethodNotImplemented():
    return JsonResponse({"error": "Method is not implemented."}, status=501)
