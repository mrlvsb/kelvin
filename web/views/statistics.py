from typing import List, Set

import pandas as pd
from bokeh.embed import file_html
from bokeh.models import Legend, Span
from bokeh.plotting import figure
from bokeh.resources import CDN
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, render

from common.models import AssignedTask, Submit, Task
from common.utils import is_teacher


def get_task_submits(task: Task) -> List[Submit]:
    return list(Submit.objects
                .filter(assignment__task_id=task.id)
                .order_by('created_at')
                .all())


def get_assignment_submits(assignment: AssignedTask) -> List[Submit]:
    return list(Submit.objects
                .filter(assignment_id=assignment.id)
                .order_by('created_at')
                .all())


def get_students(submits: List[Submit]) -> Set[User]:
    students = set()
    for submit in submits:
        if submit.student not in students:
            students.add(submit.student)
    return students


def create_submit_chart_html(submits: List[Submit], assignment: AssignedTask = None) -> str:
    frame = pd.DataFrame({
        "date": [submit.created_at for submit in submits]
    })
    frame["count"] = 1

    plot = figure(plot_width=1200, plot_height=400, x_axis_type="datetime")
    plot.line(frame["date"], frame["count"].cumsum())
    plot.yaxis.axis_label = "# submits"

    if assignment:
        line_args = dict(line_dash="dashed", line_color="red", line_width=2)
        vline = Span(location=submits[len(submits) // 2].created_at, dimension='height',
                     **line_args)
        plot.renderers.extend([vline])

        deadline = plot.line([], [], **line_args)
        legend = Legend(items=[
            ("deadline", [deadline]),
        ])

        plot.add_layout(legend, "right")

    return file_html(plot, CDN, "Submits over time")


def render_statistics(request, task, submits, assignment=None):
    students = get_students(submits)

    return render(request, 'web/teacher/statistics.html', {
        'task': task,
        'submits': submits,
        'students': students,
        'submit_plot': create_submit_chart_html(submits, assignment=assignment)
    })


@user_passes_test(is_teacher)
def for_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    submits = get_task_submits(task)
    return render_statistics(request, task, submits)


@user_passes_test(is_teacher)
def for_assignment(request, assignment_id):
    assignment = get_object_or_404(AssignedTask, pk=assignment_id)
    task = assignment.task
    submits = get_assignment_submits(assignment)
    return render_statistics(request, task, submits, assignment)
