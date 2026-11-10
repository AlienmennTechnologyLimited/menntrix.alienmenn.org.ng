from django.db import models
from django.conf import settings
import uuid


class UserLocation(models.Model):
    SOURCE_CHOICES = [
        ("login", "Login"),
        ("logout", "Logout"),
        ("heartbeat", "Heartbeat"),
        ("call", "Call"),
        ("meeting", "Meeting"),
        ("channel", "Channel"),
        ("manual", "Manual"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menntrix_locations",
    )
    session_key = models.CharField(max_length=64, blank=True, null=True)

    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    accuracy_m = models.IntegerField(null=True, blank=True)

    ip_address = models.CharField(max_length=45, blank=True, null=True)
    ip_city = models.CharField(max_length=100, blank=True, null=True)
    ip_region = models.CharField(max_length=100, blank=True, null=True)
    ip_country = models.CharField(max_length=100, blank=True, null=True)
    ip_isp = models.CharField(max_length=150, blank=True, null=True)

    user_agent = models.CharField(max_length=500, blank=True, null=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="heartbeat")

    shared_with = models.IntegerField(null=True, blank=True)
    context_id = models.CharField(max_length=64, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "menntrix_user_location"
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "source", "-created_at"]),
        ]


class SecurityLog(models.Model):
    SEVERITY_CHOICES = [
        ("info", "Info"),
        ("warn", "Warning"),
        ("critical", "Critical"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menntrix_security_events",
    )
    event_type = models.CharField(max_length=50)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default="info")

    ip_address = models.CharField(max_length=45, blank=True, null=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    details = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "menntrix_security_log"
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["event_type", "-created_at"]),
        ]


class PeerLocationShare(models.Model):
    CONTEXT_CHOICES = [
        ("call", "Call"),
        ("meeting", "Meeting"),
        ("channel", "Channel"),
    ]

    caller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menntrix_share_initiated",
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menntrix_share_received",
    )
    context_type = models.CharField(max_length=20, choices=CONTEXT_CHOICES)
    context_id = models.CharField(max_length=64)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "menntrix_peer_location_share"
        indexes = [
            models.Index(fields=["caller", "-started_at"]),
            models.Index(fields=["receiver", "-started_at"]),
        ]


class UserPrivacy(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="menntrix_privacy",
    )
    share_location_calls = models.BooleanField(default=False)
    share_location_meetings = models.BooleanField(default=False)
    share_location_channels = models.BooleanField(default=False)
    allow_location_history = models.BooleanField(default=True)
    only_connections_can_call = models.BooleanField(default=False)
    only_connections_can_message = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "menntrix_user_privacy"

    def __str__(self):
        return f"privacy({self.user_id})"

        # ============================================================
# NOTIFICATIONS, EMAIL CONFIG, ACTIVITY LOG, PUSH
# ============================================================

class EmailConfig(models.Model):
    """Runtime-editable SMTP configuration. Single row."""

    host = models.CharField(max_length=255, default="mail.alienmenn.org.ng")
    port = models.IntegerField(default=587)
    username = models.CharField(max_length=255, default="team@alienmenn.org.ng")
    password = models.CharField(max_length=500, blank=True, default="")
    use_tls = models.BooleanField(default=True)
    use_ssl = models.BooleanField(default=False)
    from_email = models.CharField(max_length=255, default="team@alienmenn.org.ng")
    from_name = models.CharField(max_length=150, default="MENNTRIX")
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "menntrix_email_config"
        verbose_name = "Email Configuration"
        verbose_name_plural = "Email Configuration"

    def __str__(self):
        return f"{self.host}:{self.port} ({'active' if self.is_active else 'inactive'})"


class Notification(models.Model):
    """In-app notification for a user."""

    VERB_CHOICES = [
        ("message", "Message"),
        ("call", "Call"),
        ("meeting", "Meeting"),
        ("meeting_invite", "Meeting invite"),
        ("channel_live", "Channel live"),
        ("channel_comment", "Channel comment"),
        ("connection_add", "New connection"),
        ("connection_remove", "Connection removed"),
        ("comment", "Comment"),
        ("mention", "Mention"),
        ("security", "Security alert"),
        ("welcome", "Welcome"),
        ("system", "System"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menntrix_notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="menntrix_notifications_sent",
    )
    verb = models.CharField(max_length=30, choices=VERB_CHOICES, default="system")
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default="")
    url = models.CharField(max_length=500, blank=True, default="")

    is_read = models.BooleanField(default=False)
    email_sent = models.BooleanField(default=False)
    push_sent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "menntrix_notification"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "is_read"]),
        ]

    def __str__(self):
        return f"{self.verb} → {self.user_id}: {self.title[:40]}"


class ActivityLog(models.Model):
    """Personal activity history for each user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menntrix_activities",
    )
    action = models.CharField(max_length=50)
    target_type = models.CharField(max_length=30, blank=True, default="")
    target_id = models.CharField(max_length=64, blank=True, default="")
    description = models.CharField(max_length=500, blank=True, default="")
    ip_address = models.CharField(max_length=45, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "menntrix_activity_log"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self):
        return f"{self.user_id} {self.action} @ {self.created_at:%Y-%m-%d %H:%M}"


class PushSubscription(models.Model):
    """Browser/device push subscription (Web Push API)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menntrix_push_subs",
    )
    endpoint = models.TextField()
    p256dh = models.TextField()
    auth = models.TextField()
    user_agent = models.CharField(max_length=500, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "menntrix_push_subscription"
        indexes = [
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user_id} sub@{self.created_at:%Y-%m-%d}"