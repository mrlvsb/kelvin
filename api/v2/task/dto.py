from ninja import Schema


class SubmitCommentCreate(Schema):
    source: str
    line: int | None
    text: str | None


class SubmitCommentUpdate(Schema):
    text: str | None
