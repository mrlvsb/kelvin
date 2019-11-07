from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),

    path('task/<str:student_username>/<int:assignment_id>', views.task_detail, name='task_detail'),
    path('task/<str:student_username>/<int:assignment_id>/<int:submit_num>', views.task_detail, name='task_detail'),

    path('task/<int:assignment_id>', views.task_detail, name='task_detail'),
    path('task/<int:assignment_id>/<int:submit_num>', views.task_detail, name='task_detail'),

    path('install_<str:token>.sh', views.script, name='install.sh'),
    path('upr.py', views.uprpy, name='upr.py'),
]
