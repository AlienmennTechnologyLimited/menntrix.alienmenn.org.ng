from django.urls import path
from . import privacy_views

urlpatterns = [
    path("privacy/", privacy_views.privacy_page, name="privacy"),
    path("privacy/location/", privacy_views.privacy_location, name="privacy_location"),
    path("privacy/security/", privacy_views.privacy_security, name="privacy_security"),
    path("privacy/clear-location/", privacy_views.privacy_clear_location, name="privacy_clear_location"),
    path("privacy/blocked/", privacy_views.privacy_blocked, name="privacy_blocked"),
    path("privacy/unblock/<int:user_id>/", privacy_views.privacy_unblock, name="privacy_unblock"),
]