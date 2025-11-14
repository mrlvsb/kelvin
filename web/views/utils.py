from django.http import HttpResponse
from unidecode import unidecode


def file_response(file, filename: str, mimetype: str) -> HttpResponse:
    response = HttpResponse(file, mimetype)
    response["Content-Disposition"] = f'attachment; filename="{unidecode(filename)}"'
    return response
