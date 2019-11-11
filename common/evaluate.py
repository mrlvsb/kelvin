import django_rq
from evaluator.evaluator import evaluate
from common.models import Submit
import json


@django_rq.job
def evaluate_job(s: Submit):
    result = evaluate(
        "tasks/{}".format(s.assignment.task.code),
        s.source.path,
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