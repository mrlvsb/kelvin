from ninja import Router, Path, Body
from serde import to_dict

from api.auth import require_submit_access
from api.v2.task.dto import SubmitCommentCreate, SubmitCommentUpdate
from common.models import Comment
from common.services.comments_service import (
    create_submit_comment,
    update_submit_comment,
    delete_submit_comment,
)

router = Router()


@router.post("", url_name="create_submit_comment")
@require_submit_access
def api_create_submit_comment(
    request,
    assignment_id: int = Path(...),
    login: str = Path(...),
    submit_num: int = Path(...),
    comment_data: SubmitCommentCreate = Body(...),
):
    comment: Comment = create_submit_comment(
        submit=request.submit_instance,
        author=request.user,
        content=comment_data.text,
        source=comment_data.source,
        line=comment_data.line,
    )

    return to_dict(comment.to_dto(can_edit=True, type=comment.type(), unread=False))


@router.put("{comment_id}", url_name="modify_submit_comment")
@require_submit_access
def api_modify_submit_comment(
    request,
    assignment_id: int = Path(...),
    login: str = Path(...),
    submit_num: int = Path(...),
    comment_id: int = Path(...),
    comment_data: SubmitCommentUpdate = Body(...),
):
    comment: Comment = update_submit_comment(
        submit=request.submit_instance,
        comment_id=comment_id,
        author=request.user,
        new_content=comment_data.text,
    )

    if comment is None:
        return None

    return to_dict(comment.to_dto(can_edit=True, type=comment.type(), unread=False))


@router.delete("{comment_id}", url_name="delete_submit_comment")
@require_submit_access
def api_delete_submit_comment(
    request,
    assignment_id: int = Path(...),
    login: str = Path(...),
    submit_num: int = Path(...),
    comment_id: int = Path(...),
):
    delete_submit_comment(comment_id=comment_id, author=request.user)
