import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "menntrix.settings.dev")

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from menntrix_calls.routing import websocket_urlpatterns as call_ws
from menntrix_meetings.routing import websocket_urlpatterns as meeting_ws
from menntrix_channels.routing import websocket_urlpatterns as channel_ws


application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(call_ws + meeting_ws + channel_ws)
    ),
})