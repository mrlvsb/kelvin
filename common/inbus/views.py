import serde.json

from django.core.cache import cache
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse

from . import inbus
from common.inbus import dto
from common.utils import is_teacher


@user_passes_test(is_teacher)
def subject_versions(request):
    subject_versions = cache.get("subject_versions")
    if not subject_versions:
        subject_versions = inbus.subject_versions()
        cache.set("subject_versions", subject_versions, 60 * 60)

    # safe=False is used because we return a list directly
    return JsonResponse(serde.to_dict(subject_versions), safe=False)


@user_passes_test(is_teacher)
def schedule_subject_by_version_id(
    request, subject_version_id: dto.SubjectVersionId, inbus_semester_id: int
):
    schedule_subject = inbus.schedule_subject_by_version_id(subject_version_id, inbus_semester_id)

    # safe=False is used because we return a list directly
    return JsonResponse(serde.to_dict(schedule_subject), safe=False)


@user_passes_test(is_teacher)
def students_in_concrete_activity(request, concrete_activity_id: dto.ConcreteActivityId):
    study_relations = inbus.students_in_concrete_activity(concrete_activity_id)

    # safe=False is used because we return a list directly
    return JsonResponse(serde.to_dict(study_relations), safe=False)
