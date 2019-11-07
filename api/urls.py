from django.urls import path

from . import views

urlpatterns = [
    path('submit/<path:task_code>', views.submit),
]
