from dataclasses import dataclass

from serde import serde


@serde
@dataclass
class CommentDTO:
    id: int
    author: str
    author_id: int
    text: str
    line: int
    source: str
    can_edit: bool
    type: str
    unread: bool
