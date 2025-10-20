from datetime import datetime
from serde import serde, field


# Class that represents a DTO for single answer in a question.
@serde
class AnswerDto:
    # Content of answer
    answer_content: str
    # Indicator if answer is correct
    is_correct: bool
    # Identifier of answer
    _id: str | None = field(default=None, skip_if=lambda x: x is None)

    # Positive and negative fields are required when question type is abcd.multiple
    # Value that is added to accumulator if the answer is not marked wrong
    positive: int | None = field(default=None, skip_if=lambda x: x is None)
    # Value that is subtracted from accumulator if the answer is marked wrong
    negative: int | None = field(default=None, skip_if=lambda x: x is None)

    @property
    def id(self):
        return self._id


# Class that represents a DTO for a question in a quiz.
@serde
class QuestionDto:
    # Content of quiz question
    content: str
    # Points of question
    points: int
    # Name of question
    name: str
    # Type of question (open, abcd, abcd.multiple)
    type: str
    # Identifier of question
    _id: str | None = field(default=None, skip_if=lambda x: x is None)
    # Answers of question
    answers: list[AnswerDto] | None = field(default=None, skip_if=lambda x: x is None)

    @property
    def id(self):
        return self._id


# Class that represents a DTO for a quiz.
@serde
class QuizDto:
    # List of quiz questions
    questions: list[QuestionDto]
    # Indicator if questions will be shuffled when generating quiz
    shuffle: bool | None = field(default=None, skip_if=lambda x: x is None)


@serde
class QuizCreateDto:
    # abbr of subject quiz is linked to
    subject: str
    # name of quiz
    name: str


# Class that represents a DTO to update a quiz.
@serde
class UpdateQuizDto:
    # Working relative directory of quiz
    quiz_directory: str
    # Indicator if questions will be shuffled when generating quiz
    shuffle: bool
    # List of quiz questions
    questions: list[QuestionDto] | None = field(default=None, skip_if=lambda x: x is None)


# Class that represents a DTO to update an assignment
@serde
class QuizClassAssignmentUpdateDto:
    # ID of class quiz should be assigned to
    id: int
    # Indicator if quiz results are published
    publish_results: bool | None = False
    # Duration of quiz (in minutes)
    duration: int | None = None
    # Deadline of quiz
    deadline: datetime | None = field(
        default=None, deserializer=lambda x: datetime.fromisoformat(x)
    )
    # Start time of quiz
    assigned: datetime | None = field(
        default=None, deserializer=lambda x: datetime.fromisoformat(x)
    )
    # ID of assignment
    assigned_id: int | None = None


# Class that represents a DTO to update an assignments
@serde
class QuizClassAssignmentsUpdateDto:
    # List of possible assignments
    assignments: list[QuizClassAssignmentUpdateDto]


# Class that represents score for a question
@serde
class ScoreDto:
    # Assigned points
    points: int | float
    # Assigned comment
    comment: str = ""


# Class that represents scoring for a quiz questions
@serde
class ScoringDto:
    # Dict of scores, key is ID of question
    scoring: dict[str, ScoreDto]


# Class that represents submitted answer
@serde
class SubmitAnswerDto:
    # Answer, which can be text or boolean value
    answer: bool | str
    # ID of answer of question in case of possible multiple answers
    id: str | None = field(default=None, skip_if=lambda x: x is None)


# Class that represents submitted answers
@serde
class SubmitAnswersDto:
    # List of submitted answers, key is ID of question
    submit: dict[str, list[SubmitAnswerDto]]
