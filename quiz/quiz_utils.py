from django.contrib.auth.models import User

from common.models import Class
from quiz.models import Quiz, AssignedQuiz, EnrolledQuiz
from web.markdown_utils import process_markdown


class QuizException(Exception):
    """
    Exception that can be raised during invalid quiz operations
    """

    pass


def quiz_assigned_classes(quiz: Quiz, requested_by: int):
    """
    Function that returns a list of classes that are/can be assigned to the quiz.
    """
    classes = Class.objects.current_semester().filter(subject=quiz.subject)
    user = User.objects.get(pk=requested_by)

    assignments_dtos = []

    for clazz in classes:
        assignment = AssignedQuiz.objects.filter(quiz=quiz.id, clazz=clazz.id)
        if assignment.count() == 0:
            assignments_dtos.append(
                {
                    "id": clazz.id,
                    "name": str(clazz),
                    "code": clazz.code,
                    "teacher": clazz.teacher.username,
                    "timeslot": clazz.timeslot,
                    "visible": clazz.teacher.id == user.id,
                    "deletable": True,
                }
            )
        elif assignment.count() == 1:
            assignment = assignment[0]
            deletable = assignment.enrolledquiz_set.count() == 0

            assignments_dtos.append(
                {
                    "id": clazz.id,
                    "name": str(clazz),
                    "assigned_id": assignment.id,
                    "assigned": str(assignment.assigned),
                    "deadline": str(assignment.deadline),
                    "duration": assignment.duration,
                    "code": clazz.code,
                    "timeslot": clazz.timeslot,
                    "teacher": clazz.teacher.username,
                    "publish_results": assignment.publish_results,
                    "visible": clazz.teacher.id == user.id,
                    "deletable": deletable,
                }
            )
        else:
            raise Exception("Multiple assignments for one class")

    assignments_dtos.sort(
        key=lambda x: (x["teacher"] != user.username, x["teacher"], "assigned" not in x)
    )

    return assignments_dtos


def score_quiz(enrolled_quiz: EnrolledQuiz):
    """
    Method that computes the score of a submitted quiz for questions that are possible to score automatically.
    Automatically scored questions are of type: abcd, abcd.multiple
    """
    if not enrolled_quiz.submitted:
        raise QuizException("Attempt to score non submitted quiz.")
    template = enrolled_quiz.template.content
    submit = enrolled_quiz.submit
    scoring = {}
    questions = template.get("questions")

    if questions is not None:
        for question in questions:
            scoring[question["_id"]] = {"points": 0.0, "comment": ""}
            submit_answers = submit.get(question["_id"])
            if submit_answers is None:
                continue
            if question["type"] == "abcd":
                for answer in question["answers"]:
                    if answer["is_correct"]:
                        for submit_answer in submit_answers:
                            if (
                                submit_answer["id"] == answer["_id"]
                                and submit_answer["answer"] is True
                            ):
                                scoring[question["_id"]]["points"] = float(question["points"])
            elif question["type"] == "abcd.multiple":
                multiplier = 0
                for answer in question["answers"]:
                    for submit_answer in submit_answers:
                        if submit_answer["id"] == answer["_id"]:
                            if submit_answer["answer"] == answer["is_correct"]:
                                multiplier += answer["positive"]
                            else:
                                multiplier -= answer["negative"]
                if multiplier < 0:
                    multiplier = 0
                elif multiplier > 100:
                    multiplier = 100

                scoring[question["_id"]]["points"] = question["points"] * multiplier / 100

    enrolled_quiz.scoring = scoring

    enrolled_quiz.save()


def quiz_to_html(quiz_directory: str, quiz: dict):
    """
    Helper function that renders a markdown content of question and its possible answers to HTML and returns it.
    """
    result = []

    for question in quiz["questions"]:
        question_render = {
            "id": question.get("_id"),
            "type": question["type"],
            "points": question["points"],
            "name": question["name"],
            "htmlContent": process_markdown(quiz_directory, question["content"], "quiz").content,
        }
        if question.get("answers"):
            answers = []
            for answer in question["answers"]:
                answers.append(
                    {
                        "id": answer.get("_id"),
                        "htmlContent": process_markdown(
                            quiz_directory, answer["answer_content"], "quiz"
                        ).content,
                    }
                )
            question_render["answers"] = answers
        result.append(question_render)

    return result
