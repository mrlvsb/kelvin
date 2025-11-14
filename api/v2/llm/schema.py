from ninja import Schema


class ModifySuggestionSchema(Schema):
    modified_text: str | None = None
