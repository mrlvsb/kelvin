from django.urls import path

from . import views

urlpatterns = [
    path('submit/<path:task_code>', views.submit),
    path('tasks/<int:task_id>', views.task_detail),
    path('tasks/', views.task_detail),
    path('tasks', views.tasks_list),
    path('info', views.info),
    path('classes', views.class_detail_list),
    path('subject/<subject_abbr>', views.subject_list),
]
