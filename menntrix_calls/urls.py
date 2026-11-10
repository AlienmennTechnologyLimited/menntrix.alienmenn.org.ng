from django.urls import path
from . import views

urlpatterns = [
    path("call/start/<int:user_id>/", views.call_start, name="call_start"),
    path("call/start/<int:user_id>/<str:call_type>/", views.call_start, name="call_start_typed"),
    path("call/<str:call_id>/", views.call_room, name="call_room"),
    path("call/<str:call_id>/ping/", views.call_ping, name="call_ping"),
    path("call/<str:call_id>/status/", views.call_status, name="call_status"),
    path("call/<str:call_id>/accept/", views.call_accept, name="call_accept"),
    path("call/<str:call_id>/reject/", views.call_reject, name="call_reject"),
    path("call/<str:call_id>/cancel/", views.call_cancel, name="call_cancel"),
    path("call/<str:call_id>/end/", views.call_end, name="call_end"),
    path("call/<str:call_id>/end-ajax/", views.call_end_ajax, name="call_end_ajax"),
    path("calls/clear-mine/", views.call_clear_mine, name="call_clear_mine"),
    path("calls/history/", views.call_history, name="call_history"),
]