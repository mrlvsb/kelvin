import datetime
import logging
import os

from django.contrib.auth.models import User as DjangoUser
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import BadRequest
from django.http import HttpRequest
from django.urls import reverse
from notifications.models import Notification
from notifications.signals import notify

from common.ai_review.dto import AIReviewResult, SubmitSummary, SuggestionState
from common.ai_review.processor import AI_REVIEW_COMMENT_AUTHOR, AI_REVIEW_COMMENT_TYPE
from common.dto import SubmitSources, ImageSource, VideoSource, TextSource, CommentDTO
from common.evaluate import evaluate_submit
from common.event_log import record_submit_event
from common.models import AssignedTask, Submit
from common.upload import upload_submit_files, mimedetector
from common.utils import is_teacher, get_client_ip_address
from evaluator.results import EvaluationResult
from kelvin.settings import MAX_INLINE_CONTENT_BYTES, MAX_INLINE_LINES

# How much time has to be elapsed between two consecutive submits.
# Note that this is not perfect due to us not using atomicity properly, but it's
# better than nothing.
SUBMIT_RATELIMIT = datetime.timedelta(seconds=30)

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


class SubmitRateLimited(Exception):
    def __init__(self, message: str, time_until_limit_expires: datetime.timedelta):
        super().__init__(message)

        self.time_until_limit_expires = time_until_limit_expires


class SubmitPastHardDeadline(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class SubmitAfterFinal(Exception):
    def __init__(self, message: str):
        super().__init__(message)


def store_submit(request: HttpRequest, assignment: AssignedTask) -> Submit:
    """
    Creates a new submit for the given `assignment` and the user logged in the `request`.
    Expects that the POST request contains a multipart form with a (potentially repeated)
    "solution" field that contains uploaded files.
    Optionally, the request can also contain a "paths" field that contains a string with a single
    path per line, assigning paths to the uploaded "solution" files.
    """
    if (
        assignment.has_hard_deadline()
        and assignment.is_past_deadline()
        and not is_teacher(request.user)
    ):
        raise SubmitPastHardDeadline("Submit was submitted after deadline")

    # Get existing submits of the student
    submits = list(
        Submit.objects.filter(assignment__pk=assignment.id, student__pk=request.user.id).order_by(
            "-created_at"
        )
    )

    # Check submit date across all tasks, just to be a bit more defensive
    last_student_submit = (
        Submit.objects.filter(student=request.user).order_by("-created_at").first()
    )

    if last_student_submit is not None:
        since_last_submit = (
            datetime.datetime.now(datetime.timezone.utc) - last_student_submit.created_at
        )
        if since_last_submit < SUBMIT_RATELIMIT:
            raise SubmitRateLimited("Submit was rate limited", SUBMIT_RATELIMIT - since_last_submit)

    if any(s.is_final for s in submits):
        raise SubmitAfterFinal("Attempt to create submit after marking previous as final")

    # TODO: transaction/better submit_num checking
    s = Submit()
    s.student = request.user
    s.assignment = assignment
    s.submit_num = len(submits) + 1
    client_ip = get_client_ip_address(request)
    if client_ip:
        s.ip_address = client_ip

    solutions = request.FILES.getlist("solution")
    tmp = request.POST.get("paths", None)
    if tmp:
        paths = [f.rstrip("\r") for f in tmp.split("\n") if f.rstrip("\r")]
    else:
        paths = [f.name for f in solutions]

    if solutions is None or len(solutions) != len(paths) or len(solutions) == 0:
        raise BadRequest("No files were uploaded")

    upload_submit_files(s, paths, solutions)

    # we need submit_id before putting the job to the queue
    s.save()
    s.jobid = evaluate_submit(request, s).id
    s.save()

    record_submit_event(
        request=request, user=request.user, task=assignment, submit_num=s.submit_num
    )

    # delete previous notifications
    Notification.objects.filter(
        action_object_object_id__in=[str(s.id) for s in submits],
        action_object_content_type=ContentType.objects.get_for_model(Submit),
        verb="submitted",
    ).delete()

    if not is_teacher(request.user):
        notify.send(
            sender=request.user,
            recipient=[assignment.clazz.teacher],
            verb="submitted",
            action_object=s,
            important=any([s.assigned_points is not None for s in submits]),
        )
    return s


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
    requester: DjangoUser,
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
                            "rating": summary.rating,
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
                            "rating": suggestion.rating,
                        }
                    },
                )
            )


def is_file_small(path: str) -> bool:
    def count_lines(path: str) -> int:
        lines = 0
        with open(path) as f:
            for line in f:
                lines += 1
        return lines

    try:
        return (
            os.path.getsize(path) <= MAX_INLINE_CONTENT_BYTES
            and count_lines(path) < MAX_INLINE_LINES
        )
    except UnicodeDecodeError:
        # probably a binary file
        return False
