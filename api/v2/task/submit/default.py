import logging
from typing import Dict, List

from django.contrib.contenttypes.models import ContentType
from ninja import Router, Path
from notifications.models import Notification
from serde import to_dict

from api.auth import get_submit_write_access
from common.comment import comment_to_dto
from common.dto import (
    AssignedSubmit,
    SubmitSources,
    TaskSubmitDetails,
    AuthUser,
    CommentDTO,
)
from common.models import Submit, Comment
from common.submit import (
    fetch_submit_sources,
    process_submit_evaluation_result,
    process_submit_review_result,
)
from web.dto import SubmitData
from web.views.student import get_submit_data

router = Router()


def fetch_submit_comments(
    requester: AuthUser,
    submit: Submit,
    sources: SubmitSources,
    notifications: Dict[int, Notification],
) -> List[CommentDTO]:
    """
    Fetches all comments associated with a submission and attaches them to relevant sources.
    General comments (not linked to files or lines) are returned separately.
    Notification state and edit permissions are annotated per comment.
    """

    summary_comments: List[CommentDTO] = []

    for comment in Comment.objects.filter(submit_id=submit.id).order_by("id"):
        is_comment_author: bool = comment.author == requester
        notification = notifications.get(comment.id, None)

        notification_id = None
        unread = False

        if notification:
            notification_id = notification.id
            unread = notification.unread

        try:
            # Comments not tied to a file go to summary section
            if not comment.source or comment.source not in sources:
                summary_comments.append(
                    comment_to_dto(
                        comment=comment,
                        can_edit=is_comment_author,
                        type=comment.type(),
                        unread=unread,
                        notification_id=notification_id,
                    )
                )
            else:
                # Bounds check in case source changed and comment references invalid line
                max_lines = sources[comment.source].content.count("\n")
                line = 0 if comment.line > max_lines else comment.line

                sources[comment.source].comments.setdefault(line - 1, []).append(
                    comment_to_dto(
                        comment=comment,
                        can_edit=is_comment_author,
                        type=comment.type(),
                        unread=unread,
                        notification_id=notification_id,
                    )
                )
        except KeyError as e:
            # Prevents failing rendering if unexpected source states occur
            logging.exception(e)

    return summary_comments


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
