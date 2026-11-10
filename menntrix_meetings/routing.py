from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"^ws/meeting/(?P<uuid>[0-9a-f]{32})/$", consumers.MeetingConsumer.as_asgi()),
]