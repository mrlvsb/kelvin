from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r'exams/ws/(?P<id>.+)', consumers.ChatConsumer),
]
