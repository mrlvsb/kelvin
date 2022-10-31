from typing import List, Set

import numpy as np
import pandas as pd
import pytz
from bokeh.embed import file_html
from bokeh.models import ColumnDataSource, HoverTool, OpenURL, Span, TapTool
from bokeh.palettes import Category20_20 as CategoricalPalette
from bokeh.plotting import figure
from bokeh.resources import CDN
from bokeh.transform import factor_cmap
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone

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


def get_student_points(submits: List[Submit]):
    student_points = {}

    for submit in submits:
        points = submit.assigned_points
        if points is not None and points >= 0:
            student_points[submit.student] = points
    return student_points


def draw_deadline_line(plot, deadline):
    line_args = dict(line_dash="dashed", line_color="red", line_width=2)
    vline = Span(location=deadline, dimension="height",
                 **line_args)
    plot.renderers.extend([vline])
    plot.line([], [], **line_args)


def create_submit_chart_html(submits: List[Submit], assignments: List[AssignedTask]) -> str:
    main_assignment = assignments[0] if assignments else None

    def format_points(submit: Submit):
        if not main_assignment or not main_assignment.max_points:
            return "not graded"
        points = submit.points or submit.assigned_points
        if points is None:
            return "no points assigned"
        return f"{points}/{main_assignment.max_points}"

    # Move the datetime to local time zone and then forcefully treat it as UTC (remove timezone
    # information) to make Bokeh render it correctly.
    frame = pd.DataFrame({
        "date": [timezone.localtime(submit.created_at).replace(tzinfo=pytz.UTC) for submit in
                 submits],
        "student": [submit.student.username for submit in submits],
        "submit_num": [submit.submit_num for submit in submits],
        "submit_url": [reverse("task_detail", kwargs=dict(
            assignment_id=submit.assignment.id,
            login=submit.student.username,
            submit_num=submit.submit_num
        ))
                       for submit in submits],
        "points": [format_points(submit) for submit in submits],
    })
    frame["count"] = 1
    frame["cumsum"] = frame["count"].cumsum()

    source = ColumnDataSource(data=frame)

    plot = figure(plot_width=1200, plot_height=400, x_axis_type="datetime",
                  tools="pan,wheel_zoom,box_zoom,save,reset,tap")
    plot.line("date", "cumsum", source=source)

    students = sorted(set(frame["student"]))
    mapper = factor_cmap(field_name="student", palette=CategoricalPalette, factors=students)
    points = plot.circle("date", "cumsum", color=mapper, source=source, size=8)
    plot.yaxis.axis_label = "# submits"

    url = "@submit_url#src"
    taptool = plot.select(type=TapTool)
    taptool.callback = OpenURL(url=url)

    hover = HoverTool(
        tooltips=[
            ("submit", "@student #@submit_num"),
            ("points", "@points"),
            ("date", "@date{%d. %m. %Y %H:%M:%S}")
        ],
        formatters={'@date': 'datetime'},
        renderers=[points]
    )
    plot.add_tools(hover)

    for assignment in assignments:
        if assignment.deadline is not None:
            draw_deadline_line(plot, assignment.deadline)

    return file_html(plot, CDN, "Submits over time")


def create_point_chart_html(student_points):
    points = sorted(student_points.values())

    plot = figure(plot_width=1200, plot_height=400)

    plot.yaxis.axis_label = "# students"

    hist, edges = np.histogram(points, bins=50)
    plot.quad(top=hist, bottom=0, left=edges[:-1], right=edges[1:],
              fill_color="navy", line_color="white", alpha=0.5)
    return file_html(plot, CDN, "Point distribution")


def render_statistics(request, task, submits, assignments):
    students = get_students(submits)
    student_points = get_student_points(submits)
    points = list(student_points.values())
    average_points = np.average(points) if points else 0

    graded_str = "no submits"
    if len(students) > 0:
        graded_str = f"{len(student_points)}/{len(students)} ({(len(student_points) / len(students)) * 100:.2f} %)"

    return render(request, 'web/teacher/statistics.html', {
        'task': task,
        'submits': submits,
        'graded': graded_str,
        'average_points': average_points,
        'submit_plot': create_submit_chart_html(submits, assignments=assignments),
        'point_plot': create_point_chart_html(student_points)
    })


@user_passes_test(is_teacher)
def for_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    submits = get_task_submits(task)
    assignments = AssignedTask.objects.filter(task_id=task_id)
    return render_statistics(request, task, submits, assignments)


@user_passes_test(is_teacher)
def for_assignment(request, assignment_id):
    assignment = get_object_or_404(AssignedTask, pk=assignment_id)
    task = assignment.task
    submits = get_assignment_submits(assignment)
    return render_statistics(request, task, submits, [assignment])
