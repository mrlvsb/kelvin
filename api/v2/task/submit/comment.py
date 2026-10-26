from ninja import Router, Path, Body
from ninja import Schema
from ninja.errors import HttpError
from serde import to_dict

from api.auth import get_submit_write_access
from common.comment import (
    comment_to_dto,
    create_submit_comment,
    update_submit_comment,
    delete_submit_comment,
)
from common.models import Comment, Submit
from common.utils import is_teacher

router = Router()


class SubmitCommentCreate(Schema):
    text: str
    source: str | None = None
    line: int | None = None


class SubmitCommentUpdate(Schema):
    text: str | None


def ensure_can_comment(request, submit: Submit):
    """
    Students cannot add or edit comments for tasks from a semester that is no longer active.
    """
    if is_teacher(request.user):
        return
    if not submit.assignment.clazz.semester.active:
        raise HttpError(403, "You cannot comment on tasks from an inactive semester.")


@router.post("", url_name="create_submit_comment")
def api_create_submit_comment(
    request,
    assignment_id: int = Path(...),
    login: str = Path(...),
    submit_num: int = Path(...),
    comment_data: SubmitCommentCreate = Body(...),
):
    submit = get_submit_write_access(request, assignment_id, login, submit_num)
    ensure_can_comment(request, submit)

    comment: Comment = create_submit_comment(
        submit=submit,
        author=request.user,
        content=comment_data.text,
        source=comment_data.source,
        line=comment_data.line,
    )

    return to_dict(comment_to_dto(comment, can_edit=True, type=comment.type(), unread=True))


@router.patch("{comment_id}", url_name="modify_submit_comment")
def api_modify_submit_comment(
    request,
    assignment_id: int = Path(...),
    login: str = Path(...),
    submit_num: int = Path(...),
    comment_id: int = Path(...),
    comment_data: SubmitCommentUpdate = Body(...),
):
    submit = get_submit_write_access(request, assignment_id, login, submit_num)
    ensure_can_comment(request, submit)

    comment: Comment | None = update_submit_comment(
        submit=submit,
        comment_id=comment_id,
        author=request.user,
        new_content=comment_data.text,
    )

    if comment is None:
        return None

    return to_dict(comment_to_dto(comment, can_edit=True, type=comment.type(), unread=True))


@router.delete("{comment_id}", url_name="delete_submit_comment")
def api_delete_submit_comment(
    request,
    assignment_id: int = Path(...),
    login: str = Path(...),
    submit_num: int = Path(...),
    comment_id: int = Path(...),
):
    # Ensure the user has write access to the submission
    get_submit_write_access(request, assignment_id, login, submit_num)

    delete_submit_comment(comment_id=comment_id, author=request.user)
