import django_rq
from evaluator.evaluator import evaluate, evaluate_score
from common.models import Submit, submit_path_parts
import os


def get_meta(user):
    return {
        'username': user.username,
    }


@django_rq.job
def evaluate_job(s: Submit):
    result_path = os.path.join(
        'submit_results',
        *submit_path_parts(s),
        f"{s.student.username}_{s.submit_num}"
    )

    result = evaluate(
        "tasks/{}".format(s.assignment.task.code),
        s.source.path,
        result_path,
        get_meta(s.student),
    )

    s.points, s.max_points = evaluate_score(result)
    s.save()