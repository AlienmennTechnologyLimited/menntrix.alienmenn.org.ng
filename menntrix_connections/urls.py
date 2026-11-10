from django.urls import path
from . import views

urlpatterns = [
    path("people/", views.people_search, name="people_search"),
    path("people/<int:user_id>/", views.profile_view, name="profile_view"),
    path("new-members/", views.new_members, name="new_members"),
    path("connections/", views.connection_list, name="connection_list"),
    path("connect/<int:user_id>/", views.connection_add, name="connection_add"),
    path("disconnect/<int:user_id>/", views.connection_remove, name="connection_remove"),
    path("block/<int:user_id>/", views.block_user, name="block_user"),
    path("report/<int:user_id>/", views.report_user, name="report_user"),
]