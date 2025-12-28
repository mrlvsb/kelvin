from typing import Dict

from django.contrib.contenttypes.models import ContentType
from ninja import Router, Path
from notifications.models import Notification
from serde import to_dict

from api.auth import get_submit_write_access
from common.dto import (
    AssignedSubmit,
    SubmitSources,
    TaskSubmitDetails,
)
from common.models import Submit
from common.submit import (
    fetch_submit_comments,
    fetch_submit_sources,
    process_submit_evaluation_result,
    process_submit_review_result,
)
from web.dto import SubmitData
from web.views.student import get_submit_data

router = Router()


@router.get("/details", url_name="retrieve_submit_details")
def api_get_submit_details(
    request, assignment_id: int = Path(...), login: str = Path(...), submit_num: int = Path(...)
):
    submit = get_submit_write_access(request, assignment_id, login, submit_num)

    # Retrieve all submits for the student
    submits: list[AssignedSubmit] = [
        AssignedSubmit(
            num=s.submit_num,
            submitted=s.created_at,
            points=s.assigned_points,
            comments=s.comment_set.count(),
        )
        for s in Submit.objects.filter(
            assignment_id=assignment_id, student__username=login
        ).order_by("submit_num")
    ]

    # Retrieve all notifications for submit, used later to mark comments as read/unread
    notifications: Dict[int, Notification] = {
        c.action_object.id: c
        for c in Notification.objects.filter(
            target_object_id=submit.id,
            target_content_type=ContentType.objects.get_for_model(Submit),
        )
    }

    # Fetch submit details
    submit_sources: SubmitSources = fetch_submit_sources(submit)
    submit_data: SubmitData = get_submit_data(submit)  # TODO: Rename to SubmitEvaluationResult?

    # Process comments, non line comments returned as summary comments
    summary_comments = fetch_submit_comments(request.user, submit, submit_sources, notifications)

    # Process evaluation results
    process_submit_evaluation_result(submit_data.results, submit_sources)
    if submit_data.ai_review:
        process_submit_review_result(
            request.user, submit_data.ai_review, submit_sources, summary_comments
        )

    details = TaskSubmitDetails(
        sources=list(submit_sources.values()),
        summary_comments=summary_comments,
        submits=submits,
        current_submit=submit_num,
        deadline=submit.assignment.deadline,
    )

    return to_dict(details)
