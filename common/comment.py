from typing import List

from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404
from notifications.models import Notification
from notifications.signals import notify

from common.dto import AuthUser, CommentDTO
from common.exceptions.http_exceptions import HttpException403
from common.models import Submit, Comment


def create_submit_comment(
    submit: Submit,
    author: AuthUser,
    content: str,
    source: str | None,
    line: int | None,
) -> Comment:
    """
    Creates a new comment attached to a submission and notifies all relevant recipients.
    The comment may reference a specific file and line when applicable.
    """

    comment = Comment(submit=submit, author=author, text=content, source=source, line=line)
    comment.save()

    # Notify all participants about the new comment, excluding the author
    notify.send(
        sender=author,
        recipient=fetch_comment_recipients(submit=submit, current_author=author),
        verb="added new",
        action_object=comment,
        target=submit,
        public=False,
        important=True,
    )

    return comment


def update_submit_comment(
    submit: Submit,
    comment_id: int,
    author: AuthUser,
    new_content: str | None,
) -> Comment | None:
    """
    Updates an existing comment if authored by the requester. When empty content is given,
    the comment is deleted instead. Existing notifications linked to the comment are cleared.
    """

    # Empty content behaves as deletion for convenience in UI workflows
    if not new_content or new_content.strip() == "":
        delete_submit_comment(comment_id, author)
        return None

    comment = get_object_or_404(Comment, id=comment_id)

    if comment.author != author:
        raise HttpException403("Only the author can update the comment")

    # Remove previous notifications so new updates re-trigger alerts
    Notification.objects.filter(
        action_object_object_id=comment.id,
        action_object_content_type=ContentType.objects.get_for_model(Comment),
    ).delete()

    if comment.text != new_content:
        comment.text = new_content
        comment.save()

        # Send updated notifications to participants
        notify.send(
            sender=author,
            recipient=fetch_comment_recipients(submit, author),
            verb="updated",
            action_object=comment,
            target=submit,
            public=False,
            important=True,
        )

    return comment


def delete_submit_comment(comment_id: int, author: AuthUser):
    """
    Deletes a comment if authored by the requester and removes related notifications.
    """

    comment = get_object_or_404(Comment, id=comment_id)

    if comment.author != author:
        raise HttpException403("Only the author can delete the comment")

    # Remove notifications linked to the comment before deletion
    Notification.objects.filter(
        action_object_object_id=comment.id,
        action_object_content_type=ContentType.objects.get_for_model(Comment),
    ).delete()

    comment.delete()


def fetch_comment_recipients(submit: Submit, current_author: AuthUser) -> List[AuthUser]:
    """
    Collects all users involved in a submission to determine who should receive notifications.
    Includes teacher, student, and all unique previous commenters except the triggering author.
    """

    # Initial recipients: teacher and student
    recipients = [submit.assignment.clazz.teacher, submit.student]

    # Include all unique past commenters
    for comment in Comment.objects.filter(submit_id=submit.id):
        if comment.author not in recipients:
            recipients.append(comment.author)

    # The sender should not receive their own notification
    recipients.remove(current_author)

    return recipients


def comment_to_dto(
    comment: Comment, can_edit: bool, type: str, unread: bool, notification_id: int | None = None
) -> CommentDTO:
    """
    Converts a Comment model instance into a CommentDTO for data transfer.
    """

    return CommentDTO(
        id=comment.id,
        author=comment.author.get_full_name(),
        author_id=comment.author.id,
        text=comment.text,
        line=comment.line,
        source=comment.source,
        can_edit=can_edit,
        type=type,
        unread=unread,
        notification_id=notification_id,
    )
