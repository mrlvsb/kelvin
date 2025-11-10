from common.models import Semester
from common.utils import is_teacher
from ninja import Router
from web.views.teacher import user_passes_test

from .dto import SemesterResponse

router = Router()


@router.get(
    "/semesters",
    response={200: list[SemesterResponse]},
    summary="Get of all semesters",
    description="Retrieve a list of all semesters.",
)
@user_passes_test(is_teacher)
def semesters(request):
    semesters = Semester.objects.all()
    semesters_response = [
        SemesterResponse(
            pk=semester.pk,
            year=semester.year,
            winter=semester.winter,
            inbus_semester_id=semester.inbus_semester_id,
        )
        for semester in semesters
    ]
    return semesters_response
