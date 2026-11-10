from django.urls import path
from . import views
from . import privacy_urls
from django.views.generic import TemplateView

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("menu/", views.menu, name="menu"),
    path("setting/", views.setting, name="setting"),
    path("setting/account/", views.account, name="account"),
    path("setting/personalinfo/", views.personalinfo, name="personalinfo"),
    path("setting/payment/", views.payment, name="payment"),
    path("setting/security/", views.security, name="security"),
    path("setting/profile-picture/", views.profile_picture, name="profile_picture"),
    path("heartbeat/", views.heartbeat, name="heartbeat"),
        # Notifications
    path("notifications/", views.notifications_page, name="notifications_page"),
    path("notifications/count/", views.notifications_unread_count, name="notifications_unread_count"),
    path("notifications/recent/", views.notifications_recent, name="notifications_recent"),
    path("notifications/read/<int:notification_id>/", views.notification_mark_read, name="notification_mark_read"),
    path("notifications/read-all/", views.notifications_mark_all_read, name="notifications_mark_all_read"),

    # Activity log
    path("activity/", views.activity_log_page, name="activity_log_page"),

    # Push subscription
    path("push/public-key/", views.push_public_key, name="push_public_key"),
    path("push/subscribe/", views.push_subscribe, name="push_subscribe"),
    path("push/unsubscribe/", views.push_unsubscribe, name="push_unsubscribe"),
    path("share/<str:kind>/<str:pk>/", views.share_link, name="share_link"),
] + privacy_urls.urlpatterns

urlpatterns += [
    path(
        "menntrix-sw.js",
        TemplateView.as_view(
            template_name="menntrix-sw.js",
            content_type="application/javascript",
        ),
        name="service_worker",
    ),
]