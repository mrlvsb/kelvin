import serde.json

from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponse

from . import inbus
from common.inbus import dto
from common.utils import is_teacher


@user_passes_test(is_teacher)
def subject_versions(request):
    subject_versions = inbus.subject_versions()

    # TODO: When upgrading, see: https://docs.djangoproject.com/en/4.2/ref/request-response/#httpresponse-objects
    # for a way to set content type.
    return HttpResponse(serde.json.to_json(subject_versions),
                        content_type="application/json")


@user_passes_test(is_teacher)
def schedule_subject_by_version_id(request, subject_version_id: dto.SubjectVersionId):
    schedule_subject = inbus.schedule_subject_by_version_id(subject_version_id)

    # TODO: When upgrading, see: https://docs.djangoproject.com/en/4.2/ref/request-response/#httpresponse-objects
    # for a way to set content type.
    return HttpResponse(serde.json.to_json(schedule_subject),
                        content_type="application/json")


@user_passes_test(is_teacher)
def students_in_concrete_activity(request, concrete_activity_id: dto.ConcreteActivityId):
    study_relations = inbus.students_in_concrete_activity(concrete_activity_id)

    # TODO: When upgrading, see: https://docs.djangoproject.com/en/4.2/ref/request-response/#httpresponse-objects
    # for a way to set content type.
    return HttpResponse(serde.json.to_json(study_relations),
                        content_type="application/json")
