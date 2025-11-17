from ninja import Schema


class CommentDTO(Schema):
    id: int
    author: str
    author_id: int
    text: str
    line: int
    source: str
    can_edit: bool
    type: str
    unread: bool
