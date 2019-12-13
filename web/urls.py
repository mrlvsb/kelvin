from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),

    path('task/<str:student_username>/<int:assignment_id>', views.task_detail, name='task_detail'),
    path('task/<str:student_username>/<int:assignment_id>/<int:submit_num>', views.task_detail, name='task_detail'),

    path('task/<int:assignment_id>', views.task_detail, name='task_detail'),
    path('task/<int:assignment_id>/<int:submit_num>', views.task_detail, name='task_detail'),

    path('teacher/task/<int:task_id>', views.teacher_task, name='teacher_task'),

    path('moss_send/<int:assignment_id>', views.moss_check, name='moss_check'),

    path('submits', views.submits),

    path('assignment/download/<int:assignment_id>', views.download_assignment_submits, name='download_assignment_submits'),
    path('assignment/download/<int:assignment_id>/csv', views.download_csv_per_task, name='download_csv_per_task'),
    path('assignment/show/<int:assignment_id>', views.show_assignment_submits, name='show_assignment_submits'),

    path('class/download/<int:class_id>/csv', views.download_csv_per_class, name='download_csv_per_class'),



    path('install_<str:token>.sh', views.script, name='install.sh'),
    path('upr.py', views.uprpy, name='upr.py'),
    path('project/<str:project_type>', views.project, name='project'),
]
