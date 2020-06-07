from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('uploads/<path:exam_id>/<str:student>/<str:filename>', views.show_upload, name='exam_upload'),
]
