import serde.json

from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponse

from . import inbus
from common.utils import is_teacher


@user_passes_test(is_teacher)
def subject_versions(request):
    subject_versions = inbus.subject_versions()

    # TODO: When upgrading, see: https://docs.djangoproject.com/en/4.2/ref/request-response/#httpresponse-objects
    # for a way to set content type.
    return HttpResponse(serde.json.to_json(subject_versions),
                        content_type="application/json")