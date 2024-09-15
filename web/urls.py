from django.urls import path

from .views import plagcheck
from .views import teacher as teacher_view
from .views import student as student_view
from .views import notification as notification_view
from .views import common as common_view
from .views import statistics as statistics_view

urlpatterns = [
    path("", common_view.index, name="index"),
    path("student-view", student_view.student_index, name="student_index"),
    path(
        "find-task/<int:task_id>/<str:login>/",
        student_view.find_task_detail,
        name="find_task_detail",
    ),
    path("task/<int:assignment_id>/<str:login>/", student_view.task_detail, name="task_detail"),
    path(
        "task/<int:assignment_id>/<str:login>/<int:submit_num>/",
        student_view.task_detail,
        name="task_detail",
    ),
    path(
        "task/<int:assignment_id>/<str:login>/<int:submit_a>-<int:submit_b>.diff",
        student_view.submit_diff,
        name="submits_diff",
    ),
    path(
        "task/<int:assignment_id>/<str:login>/<int:submit_num>/download",
        student_view.submit_download,
        name="submit_download",
    ),
    path(
        "task/<int:assignment_id>/<str:login>/<int:submit_num>/comments",
        student_view.submit_comments,
        name="submit_comments",
    ),
    path(
        "task/<int:assignment_id>/<str:login>/<int:submit_num>/result", student_view.upload_results
    ),
    path("task/<path:task_name>/asset/<path:path>", student_view.task_asset, name="task_asset"),
    path(
        "task/<path:task_name>/tests/<str:test_name>/<str:file>",
        student_view.raw_test_content,
        name="raw_test_content",
    ),
    path("task/<path:task_name>.tar.gz", student_view.tar_test_data, name="tar_test_data"),
    path(
        "result/<int:submit_id>/<str:test_name>/<str:result_type>/<str:file>",
        student_view.raw_result_content,
        name="raw_result_content",
    ),
    path(
        "submit/<int:submit_id>/source/<path:path>",
        student_view.submit_source,
        name="submit_source",
    ),
    path("submit/<int:submit_id>/pipeline", student_view.pipeline_status),
    # notifications
    path("notification/all", notification_view.all_notifications),
    path("notification/mark_as_read", notification_view.mark_as_read),
    path("notification/mark_as_read/<int:notification_id>", notification_view.mark_as_read),
    # teacher
    path("teacher/task/<int:task_id>", teacher_view.teacher_task, name="teacher_task"),
    path("teacher/task/<int:task_id>.tar", student_view.teacher_task_tar, name="teacher_task_tar"),
    path("teacher/task/<int:task_id>/moss", moss.task_moss_check, name="teacher_task_moss_check"),
    path(
        "teacher/task/<int:task_id>/moss/graph",
        moss.task_moss_graph,
        name="teacher_task_moss_graph",
    ),
    path(
        "teacher/task/<int:task_id>/moss/match/<int:match_id>/<path:path>",
        moss.task_moss_result,
        name="teacher_task_moss_result",
    ),
    path("submits", teacher_view.submits, name="submits"),
    path("submits/<str:student_username>", teacher_view.submits, name="submits"),
    path("statistics/task/<int:task_id>", statistics_view.for_task, name="task_stats"),
    path(
        "statistics/assignment/<int:assignment_id>",
        statistics_view.for_assignment,
        name="assignment",
    ),
    path(
        "assignment/download/<int:assignment_id>",
        teacher_view.download_assignment_submits,
        name="download_assignment_submits",
    ),
    path(
        "assignment/download/<int:assignment_id>/csv",
        teacher_view.download_csv_per_assignment,
        name="download_csv_per_assignment",
    ),
    path(
        "assignment/show/<int:assignment_id>",
        teacher_view.show_assignment_submits,
        name="show_assignment_submits",
    ),
    path("task/show/<int:task_id>", teacher_view.show_task_submits, name="show_task_submits"),
    path(
        "submit/<int:submit_id>/points",
        teacher_view.submit_assign_points,
        name="submit_assign_points",
    ),
    path(
        "class/download/<int:class_id>/csv",
        teacher_view.download_csv_per_class,
        name="download_csv_per_class",
    ),
    path(
        "task/<int:task_id>/csv", teacher_view.download_csv_per_task, name="download_csv_per_task"
    ),
    path("tasks", teacher_view.all_tasks, name="tasks"),
    path("tasks/<str:subject__abbr>", teacher_view.all_tasks, name="tasks"),
    path("reevaluate/<int:submit_id>", teacher_view.reevaluate, name="reevaluate"),
    path("api_token", common_view.api_token, name="api_token"),
]
