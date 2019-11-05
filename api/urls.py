from django.urls import path

from . import views

urlpatterns = [
    path('submit/<int:task_num>', views.submit),
]
