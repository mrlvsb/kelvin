from django.urls import path, re_path

from .views import teacher as teacher_view
from .views import student as student_view
from .views import notification as notification_view
from .views import common as common_view

urlpatterns = [
    path('', common_view.index, name='index'),

    path('task/<str:student_username>/<int:assignment_id>', student_view.task_detail, name='task_detail'),
    path('task/<str:student_username>/<int:assignment_id>/<int:submit_num>', student_view.task_detail, name='task_detail'),

    path('task/<int:assignment_id>', student_view.task_detail, name='task_detail'),
    path('task/<int:assignment_id>/<int:submit_num>', student_view.task_detail, name='task_detail'),
    path('task/<path:task_name>.tar.gz', student_view.tar_test_data, name='tar_test_data'),
    path('task/<path:task_name>/asset/<path:path>', student_view.task_asset, name='task_asset'),
    path('task/<path:task_name>/tests/<str:test_name>/<str:file>', student_view.raw_test_content, name='raw_test_content'),
    path('result/<int:submit_id>/<str:test_name>/<str:result_type>/<str:file>', student_view.raw_result_content, name='raw_result_content'),
    path('task/<int:assignment_id>/<str:login>/<int:submit_num>/download', student_view.submit_download, name='submit_download'),
    path('task/<int:assignment_id>/<str:login>/<int:submit_num>/comments', student_view.submit_comments, name='submit_comments'),

    # notifications
    path('notification/all', notification_view.all_notifications),
    path('notification/mark_as_read', notification_view.mark_as_read),
    path('notification/mark_as_read/<int:notification_id>', notification_view.mark_as_read),

    # teacher
    path('all', lambda req: teacher_view.teacher_list(req, teacher_id=None)),
    path('subject/<str:subject__abbr>', teacher_view.teacher_list, name='teacher_index'),
    re_path('^semester/(?P<semester__year>[0-9]{4})/(?P<semester__winter>W|S)$', teacher_view.teacher_list),
    re_path('^semester/(?P<semester__year>[0-9]{4})/(?P<semester__winter>W|S)/all$', lambda req, **kwargs: teacher_view.teacher_list(req, teacher_id=None, **kwargs)),
    re_path('^semester/(?P<semester__year>[0-9]{4})/(?P<semester__winter>W|S)/(?P<subject__abbr>[A-Z0-9]+)$', teacher_view.teacher_list),
    re_path('^semester/(?P<semester__year>[0-9]{4})/(?P<semester__winter>W|S)/(?P<subject__abbr>[A-Z0-9]+)/all$', lambda req, **kwargs: teacher_view.teacher_list(req, teacher_id=None, **kwargs)),

    path('teacher/task/<int:task_id>', teacher_view.teacher_task, name='teacher_task'),
    path('teacher/task/<int:task_id>/moss', teacher_view.teacher_task_moss_check, name='teacher_task_moss_check'),
    path('moss_send/<int:assignment_id>', teacher_view.moss_check, name='moss_check'),
    path('submits', teacher_view.submits, name='submits'),
    path('submits/<str:student_username>', teacher_view.submits, name='submits'),

    path('assignment/download/<int:assignment_id>', teacher_view.download_assignment_submits, name='download_assignment_submits'),
    path('assignment/download/<int:assignment_id>/csv', teacher_view.download_csv_per_task, name='download_csv_per_task'),
    path('assignment/show/<int:assignment_id>', teacher_view.show_assignment_submits, name='show_assignment_submits'),
    path('submit/<int:submit_id>/points', teacher_view.submit_assign_points, name='submit_assign_points'),

    path('class/download/<int:class_id>/csv', teacher_view.download_csv_per_class, name='download_csv_per_class'),

    path('tasks', teacher_view.all_tasks, name='tasks'),

    path('reevaluate/<int:submit_id>', teacher_view.reevaluate, name='reevaluate'),

    path('api_token', common_view.api_token),

    # cli support
    path('install_<str:token>.sh', student_view.script, name='install.sh'),
    path('upr.py', student_view.uprpy, name='upr.py'),

    path('project/<str:project_type>', student_view.project, name='project'),
]
