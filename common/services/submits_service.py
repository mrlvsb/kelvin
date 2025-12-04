import logging
from typing import Dict, List

from django.urls import reverse
from notifications.models import Notification

from common.ai_review.dto import AIReviewResult, SubmitSummary, SuggestionState
from common.ai_review.processor import AI_REVIEW_COMMENT_AUTHOR, AI_REVIEW_COMMENT_TYPE
from common.dto import SubmitSources, ImageSource, VideoSource, TextSource, CommentDTO, AuthUser
from common.models import Submit, Comment
from common.upload import mimedetector
from common.utils import is_teacher
from evaluator.results import EvaluationResult
from web.views.student import is_file_small

SUPPORTED_IMAGES = [
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/svg+xml",
]

SOURCE_PRIORITY = {
    "video": 0,
    "img": 1,
    "source": 2,
}


def fetch_submit_sources(submit: Submit) -> SubmitSources:
    """
    Loads all files from a submission and categorizes them into image, video or text-based sources.
    Small text files are loaded into memory while larger ones are referenced via URL.
    Unsupported image formats are served through a conversion proxy.
    """

    result: SubmitSources = {}

    for source in submit.all_sources():
        mime_type: str | None = mimedetector.from_file(source.phys)

        # Image handling
        if mime_type and mime_type.startswith("image/"):
            source_url: str = reverse("submit_source", args=[submit.id, source.virt])

            # Append conversion on unsupported formats
            if mime_type not in SUPPORTED_IMAGES:
                source_url = f"{source_url}?convert=1"

            result[source.virt] = ImageSource(path=source.virt, src=source_url)

        # Video handling
        elif mime_type and mime_type.startswith("video/"):
            # Group multiple chunks (e.g. separate streams with same basename)
            base_name: str = ".".join(source.virt.split(".")[:-1])

            if base_name not in result:
                result[base_name] = VideoSource(path=base_name)

            video_source: VideoSource = result[base_name]
            video_source.sources.append(reverse("submit_source", args=[submit.id, source.virt]))

        # Text / fallback handling
        else:
            content_text: str = ""
            content_url: str | None = None
            content_error: str | None = None

            try:
                # Load file contents when small enough, otherwise defer to URL
                if is_file_small(source.phys):
                    with open(source.phys) as file_stream:
                        content_text = file_stream.read()
                else:
                    content_url = reverse("submit_source", args=[submit.id, source.virt])
            except UnicodeDecodeError:
                content_error = "The file contains binary data or is not encoded in UTF-8"
            except FileNotFoundError:
                content_error = "Source code not found"

            result[source.virt] = TextSource(
                path=source.virt, content=content_text, content_url=content_url, error=content_error
            )

    # Sorting ensures predictable ordering in the UI
    result = dict(
        sorted(result.items(), key=lambda item: (SOURCE_PRIORITY.get(item[1].type, 99), item[0]))
    )

    return result


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
                    comment.to_dto(
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
                    comment.to_dto(
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


def process_submit_evaluation_result(result: EvaluationResult, sources: SubmitSources):
    """
    Inserts automated evaluation comments generated by backend evaluators into text sources.
    Only text-based sources are supported for automated comments.
    """

    def process_text_source(text_source: TextSource, comment: dict):
        # TODO: Comment should be dataclass instead of dict, fix when refactoring pipeline evaluation

        try:
            # Ensures indexing stays within valid line count
            line = min(text_source.content.count("\n"), int(comment["line"])) - 1

            # Prevent duplicate automated messages
            if not any(
                filter(
                    lambda c: c["text"] == comment["text"],
                    text_source.comments.setdefault(line, []),
                )
            ):
                text_source.comments.setdefault(line, []).append(
                    CommentDTO(
                        author="Kelvin",
                        author_id=-1,
                        text=comment["text"],
                        line=None,
                        source=None,
                        type="automated",
                        unread=False,
                        can_edit=False,
                        meta={"url": comment.get("url", None)},
                    )
                )
        except KeyError as e:
            logging.exception(e)

    for pipe in result:
        for source, comments in pipe.comments.items():
            for comment in comments:
                # Skip if source not present in processed sources output
                if source not in result:
                    continue

                # Only text sources are supported for automated comments
                if isinstance(sources[source], TextSource):
                    process_text_source(sources[source], comment)


def process_submit_review_result(
    requester: AuthUser,
    result: AIReviewResult,
    sources: SubmitSources,
    summary_comments: list[CommentDTO],
):
    """
    Integrates AI review results into submission data. Summary feedback is stored in summary view
    while inline suggestions attach to specific lines when visible to teachers with permissions.
    """

    summary: SubmitSummary = result.summary

    # Teachers must explicitly have permission and suggestion must be pending
    def can_view_suggestion(state: SuggestionState, user) -> bool:
        return (
            is_teacher(user)
            and user.has_perm("common.view_suggestedcomment")
            and state is SuggestionState.PENDING
        )

    if can_view_suggestion(summary.state, requester):
        if len(result.summary.text) > 0:
            summary_comments.append(
                CommentDTO(
                    author=AI_REVIEW_COMMENT_AUTHOR,
                    author_id=-1,
                    text=summary.text,
                    line=None,
                    source=None,
                    type=AI_REVIEW_COMMENT_TYPE,
                    unread=False,
                    can_edit=False,
                    meta={
                        "review": {
                            "id": summary.id,
                            "state": summary.state.name,
                        }
                    },
                )
            )

    for suggestion in result.suggestions:
        # Skip suggestions referring to unavailable or filtered sources
        if suggestion.source not in sources:
            continue

        if can_view_suggestion(suggestion.state, requester):
            sources[suggestion.source].comments.setdefault(suggestion.line - 1, []).append(
                CommentDTO(
                    author=AI_REVIEW_COMMENT_AUTHOR,
                    author_id=-1,
                    text=suggestion.text,
                    line=None,
                    source=None,
                    type=AI_REVIEW_COMMENT_TYPE,
                    unread=False,
                    can_edit=False,
                    meta={
                        "review": {
                            "id": suggestion.id,
                            "state": suggestion.state.name,
                        }
                    },
                )
            )
