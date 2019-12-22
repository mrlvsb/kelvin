from django.urls import path

from .views import teacher as teacher_view
from .views import student as student_view
from .views import common as common_view

urlpatterns = [
    path('', common_view.index, name='index'),

    path('task/<str:student_username>/<int:assignment_id>', student_view.task_detail, name='task_detail'),
    path('task/<str:student_username>/<int:assignment_id>/<int:submit_num>', student_view.task_detail, name='task_detail'),

    path('task/<int:assignment_id>', student_view.task_detail, name='task_detail'),
    path('task/<int:assignment_id>/<int:submit_num>', student_view.task_detail, name='task_detail'),
    path('task/<slug:task_name>/tests/<str:test_name>/<str:file>', student_view.raw_test_content, name='raw_test_content'),



    # teacher
    path('teacher/task/<int:task_id>', teacher_view.teacher_task, name='teacher_task'),
    path('moss_send/<int:assignment_id>', teacher_view.moss_check, name='moss_check'),
    path('submits', teacher_view.submits, name='submits'),

    path('assignment/download/<int:assignment_id>', teacher_view.download_assignment_submits, name='download_assignment_submits'),
    path('assignment/download/<int:assignment_id>/csv', teacher_view.download_csv_per_task, name='download_csv_per_task'),
    path('assignment/show/<int:assignment_id>', teacher_view.show_assignment_submits, name='show_assignment_submits'),

    path('class/download/<int:class_id>/csv', teacher_view.download_csv_per_class, name='download_csv_per_class'),

    path('tasks', teacher_view.all_tasks),

    path('reevaluate/<int:submit_id>', teacher_view.reevaluate, name='reevaluate'),

    # cli support
    path('install_<str:token>.sh', student_view.script, name='install.sh'),
    path('upr.py', student_view.uprpy, name='upr.py'),

    path('project/<str:project_type>', student_view.project, name='project'),
]
