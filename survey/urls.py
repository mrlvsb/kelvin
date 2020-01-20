from django.urls import path

from . import views

urlpatterns = [
    path('', views.survey_list),
    path('<str:survey_file>.edison.csv', views.show_edison_csv),
    path('<str:survey_file>.csv', views.show_csv),
    path('<str:survey_file>', views.show, name='survey_show'),
]
