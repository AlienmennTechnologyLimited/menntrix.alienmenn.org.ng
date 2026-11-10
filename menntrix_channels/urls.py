from django.urls import path
from . import views

urlpatterns = [
    path("channels/", views.channel_browse, name="channel_browse"),
    path("channels/mine/", views.channel_mine, name="channel_mine"),
    path("channels/create/", views.channel_create, name="channel_create"),
    path("channel/<slug:slug>/", views.channel_watch, name="channel_watch"),
    path("channel/<slug:slug>/go-live/", views.channel_go_live, name="channel_go_live"),
    path("channel/<slug:slug>/end/", views.channel_end_stream, name="channel_end_stream"),
    path("channel/<slug:slug>/subscribe/", views.channel_subscribe, name="channel_subscribe"),
    path("channel/<slug:slug>/unsubscribe/", views.channel_unsubscribe, name="channel_unsubscribe"),
]