from django.urls import path

from . import views

urlpatterns = [
    path('submit/<path:task_code>', views.submit),
    path('tasks/<int:task_id>', views.task_detail),
    path('tasks/<int:task_id>/duplicate', views.duplicate_task),
    path('tasks/', views.task_detail),
    path('tasks', views.tasks_list),
    path('info', views.info),
    path('classes', views.class_detail_list),
    path('classes/all', views.all_classess),
    path('classes/<int:class_id>/add_students', views.add_student_to_class),
    path('subject/<subject_abbr>', views.subject_list),
]
