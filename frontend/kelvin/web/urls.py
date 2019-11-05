from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('ll', views.ll, name='ll'),
    path('task/<int:id>', views.task_detail, name='task_detail'),
    path('task/<int:id>/<int:submit_id>', views.task_detail, name='task_detail'),
    path('install_<str:token>.sh', views.script, name='install.sh'),
    path('upr.py', views.uprpy, name='upr.py'),

]
