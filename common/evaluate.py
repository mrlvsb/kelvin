import django_rq
from evaluator.evaluator import evaluate
from common.models import Submit
import json


def get_meta(user):
    return {
        'username': user.username,
    }

@django_rq.job
def evaluate_job(s: Submit):
    result = evaluate(
        "tasks/{}".format(s.assignment.task.code),
        s.source.path,
        get_meta(s.student),
    )

    s.result = json.dumps(result, indent=4)

    # calculate points
    s.points = 0
    s.max_points = 0
    for i in result:
        for test in i['tests']:
            if test['success']:
                s.points += 1
            s.max_points += 1

    s.save()