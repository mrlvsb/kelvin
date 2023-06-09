from django.urls import path

from . import views

urlpatterns = [
    path('tasks/<int:task_id>', views.task_detail),
    path('tasks/<int:task_id>/duplicate', views.duplicate_task),
    path('tasks/', views.task_detail),
    path('tasks', views.tasks_list),
    path('info', views.info),
    path('classes', views.class_detail_list),
    path('classes/all', views.all_classes),
    path('classes/<int:class_id>/add_students', views.add_student_to_class),
    path('subject/<subject_abbr>', views.subject_list),
    path('subjects/all', views.subjects_all),
    path('reevaluate_task/<int:task_id>', views.reevaluate_task),
    path('search', views.search),
    path('transfer_students', views.transfer_students),
]
