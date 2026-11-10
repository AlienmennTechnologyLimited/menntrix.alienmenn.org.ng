from django.urls import path
from . import views

urlpatterns = [
    path("meetings/", views.meeting_list, name="meeting_list"),
    path("meeting/create/", views.meeting_create, name="meeting_create"),
    path("meeting/<str:uuid>/", views.meeting_room, name="meeting_room"),
    path("meeting/<str:uuid>/leave/", views.meeting_leave, name="meeting_leave"),
    path("meeting/<str:uuid>/end/", views.meeting_end, name="meeting_end"),
    path("meeting/<str:uuid>/lock/", views.meeting_toggle_lock, name="meeting_toggle_lock"),
]