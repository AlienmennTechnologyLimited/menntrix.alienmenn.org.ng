from django.urls import path
from . import views

urlpatterns = [
    path("", views.splash, name="index"),
    path("home/", views.home, name="home"),
    path("signin/", views.signin_view, name="signin"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),

    # Admin user management
    path("admin/users/", views.admin_users, name="admin_users"),
    path("admin/users/<int:user_id>/", views.admin_user_edit, name="admin_user_edit"),
]