from django.http import HttpResponse
from unidecode import unidecode

from web.markdown_utils import process_markdown


def file_response(file, filename: str, mimetype: str) -> HttpResponse:
    response = HttpResponse(file, mimetype)
    response["Content-Disposition"] = f'attachment; filename="{unidecode(filename)}"'
    return response


# Helper function that renders a markdown content of question and its possible answers to HTML and returns it.
def quiz_to_html(quiz_directory: str, quiz: dict):
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
