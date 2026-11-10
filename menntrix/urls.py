from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


# ============================================================
# MENNTRIX ADMIN BRANDING
# ============================================================
admin.site.site_header = "MENNTRIX Admin"
admin.site.site_title = "MENNTRIX Admin"
admin.site.index_title = "Welcome to MENNTRIX Admin"


# ============================================================
# URL ROUTES
# ============================================================
urlpatterns = [
    path("admin/", admin.site.urls),

    # Public + auth (index, home, signin, signup, logout)
    path("", include("menntrix_accounts.urls")),

    # Core app (dashboard, menu, settings, notifications, activity, heartbeat, privacy)
    path("", include("menntrix_core.urls")),

    # People, connections, search
    path("", include("menntrix_connections.urls")),

    # Email-style messaging
    path("", include("menntrix_messaging.urls")),

    # 1-to-1 calls + listener
    path("", include("menntrix_calls.urls")),

    # Group meetings
    path("", include("menntrix_meetings.urls")),

    # Live channels
    path("", include("menntrix_channels.urls")),

    # Earnings
    path("earnings/", include("menntrix_revenue.urls")),
]


# ============================================================
# MEDIA FILES IN DEV
# ============================================================
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.STATIC_ROOT)