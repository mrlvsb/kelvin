from typing import List
from serde import serde, field


# Class that represents a DTO for single answer in a question.
@serde
class AnswerDto:
    answer_content: str
    is_correct: bool
    _id: str | None = field(default=None, skip_if=lambda x: x is None)
    positive: int | None = field(default=None, skip_if=lambda x: x is None)
    negative: int | None = field(default=None, skip_if=lambda x: x is None)

    @property
    def id(self):
        return self._id


# Class that represents a DTO for a question in a quiz.
@serde
class QuestionDto:
    content: str
    points: int
    name: str
    type: str
    _id: str | None = field(default=None, skip_if=lambda x: x is None)
    answers: List[AnswerDto] | None = field(default=None, skip_if=lambda x: x is None)

    @property
    def id(self):
        return self._id


# Class that represents a DTO for a quiz.
@serde
class QuizDto:
    questions: List[QuestionDto]
    shuffle: bool | None = field(default=None, skip_if=lambda x: x is None)


# Class that represents a DTO to update a quiz.
@serde
class UpdateQuizDto:
    quiz_directory: str
    shuffle: bool
    questions: List[QuestionDto] | None = field(default=None, skip_if=lambda x: x is None)
