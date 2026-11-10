from django.contrib import admin
from django.utils.html import format_html
from .models import (
    UserLocation, SecurityLog, PeerLocationShare, UserPrivacy,
    EmailConfig, Notification, ActivityLog, PushSubscription,
)


@admin.register(EmailConfig)
class EmailConfigAdmin(admin.ModelAdmin):
    list_display = ("host", "port", "from_email", "is_active", "updated_at")
    fieldsets = (
        ("SMTP Server", {
            "fields": ("host", "port", "username", "password", "use_tls", "use_ssl")
        }),
        ("Sender Identity", {
            "fields": ("from_name", "from_email")
        }),
        ("Status", {
            "fields": ("is_active",)
        }),
    )

    def has_add_permission(self, request):
        # Only one row
        return not EmailConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "verb", "title", "is_read", "email_sent", "push_sent", "created_at")
    list_filter = ("verb", "is_read", "email_sent", "push_sent")
    search_fields = ("title", "body", "user__email", "user__username")
    readonly_fields = ("created_at", "email_sent", "push_sent")


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "action", "target_type", "target_id", "ip_address", "created_at")
    list_filter = ("action", "target_type")
    search_fields = ("user__email", "user__username", "description")
    readonly_fields = ("created_at",)


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "is_active", "user_agent", "created_at", "last_seen_at")
    list_filter = ("is_active",)
    search_fields = ("user__email", "user__username")


# Existing registrations (keep if not already registered elsewhere)
try:
    admin.site.register(UserLocation)
except admin.sites.AlreadyRegistered:
    pass

try:
    admin.site.register(SecurityLog)
except admin.sites.AlreadyRegistered:
    pass

try:
    admin.site.register(PeerLocationShare)
except admin.sites.AlreadyRegistered:
    pass

try:
    admin.site.register(UserPrivacy)
except admin.sites.AlreadyRegistered:
    pass

