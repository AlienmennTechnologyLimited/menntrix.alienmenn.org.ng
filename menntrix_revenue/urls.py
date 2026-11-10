from django.urls import path
from . import views

urlpatterns = [
    path("", views.my_earnings, name="my_earnings"),
]