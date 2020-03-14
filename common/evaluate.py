import django_rq
from evaluator.evaluator import evaluate, evaluate_score
from common.models import Submit
import os


def get_meta(login):
    return {
        'login': login,
    }


@django_rq.job
def evaluate_job(s: Submit):
    result_path = os.path.join(
        'submit_results',
        *s.path_parts(),
    )

    result = evaluate(
        "tasks/{}".format(s.assignment.task.code),
        s.dir(),
        result_path,
        get_meta(s.student.username),
    )

    s.points, s.max_points = evaluate_score(result)
    s.save()
