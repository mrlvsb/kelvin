import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any, Union

from serde import serde, Untagged


@serde
@dataclass
class CommentDTO:
    author: str
    author_id: int
    text: str
    line: int | None
    source: str | None
    type: str
    unread: bool
    can_edit: bool
    notification_id: int | None = None
    meta: Dict[str, Any] = field(default_factory=dict)
    id: int = -1


@serde
@dataclass
class AssignedSubmit:
    num: int
    submitted: datetime.datetime
    points: float | None
    comments: int


@serde
@dataclass
class ImageSource:
    path: str
    src: str
    type: str = "img"


@serde
@dataclass
class VideoSource:
    path: str
    sources: List[str] = field(default_factory=list)
    type: str = "video"


@serde
@dataclass
class TextSource:
    path: str
    content: str
    content_url: str | None
    error: str | None
    comments: Dict[int, List[CommentDTO]] = field(default_factory=dict)
    type: str = "source"


type SubmitSources = Dict[str, Union[ImageSource, VideoSource, TextSource]]


@serde(tagging=Untagged)
@dataclass
class TaskSubmitDetails:
    sources: List[Union[ImageSource, VideoSource, TextSource]]
    summary_comments: List[CommentDTO]
    submits: list[AssignedSubmit]
    current_submit: int
    deadline: datetime.datetime | None
