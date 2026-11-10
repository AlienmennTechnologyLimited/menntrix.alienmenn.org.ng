import re
from django.db import models
from django.conf import settings
from django.utils.text import slugify


def make_slug(text):
    """Return a URL-safe slug from any text."""
    base = slugify(text) or "channel"
    base = re.sub(r"[^a-z0-9\-]", "", base)
    return base[:60] or "channel"


# ============================================================
# CHANNEL
# ============================================================
class Channel(models.Model):
    """A live video channel owned by one user."""

    slug = models.SlugField(max_length=60, unique=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menntrix_channels_owned",
    )
    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, default="")

    is_active = models.BooleanField(default=True)      # channel page live
    is_live = models.BooleanField(default=False)       # stream currently running

    # Denormalized counters (fast reads, updated on events)
    subscriber_count = models.IntegerField(default=0)
    comment_count = models.IntegerField(default=0)
    view_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    last_stream_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "menntrix_channel"
        indexes = [
            models.Index(fields=["owner", "created_at"]),
            models.Index(fields=["is_live"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return f"#{self.slug} ({self.owner_id})"


# ============================================================
# CHANNEL COMMENT
# ============================================================
class ChannelComment(models.Model):
    """A comment on a channel page."""

    channel = models.ForeignKey(
        Channel, on_delete=models.CASCADE, related_name="comments"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "menntrix_channel_comment"
        indexes = [models.Index(fields=["channel", "created_at"])]

    def __str__(self):
        return f"#{self.id} on {self.channel_id} by {self.user_id}"


# ============================================================
# CHANNEL VIEWER
# ============================================================
class ChannelViewer(models.Model):
    """Who joined the channel page, when."""

    channel = models.ForeignKey(
        Channel, on_delete=models.CASCADE, related_name="viewers"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "menntrix_channel_viewer"
        unique_together = ("channel", "user")
        indexes = [models.Index(fields=["channel", "left_at"])]


# ============================================================
# CHANNEL STREAM SESSION
# ============================================================
class ChannelStreamSession(models.Model):
    """A single go-live session on a channel (SFU-ready)."""

    TRANSPORT_CHOICES = [
        ("mesh", "WebRTC Mesh"),
        ("sfu", "SFU"),
    ]

    channel = models.ForeignKey(
        Channel, on_delete=models.CASCADE, related_name="streams"
    )
    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    transport = models.CharField(
        max_length=10, choices=TRANSPORT_CHOICES, default="mesh"
    )

    # SFU placeholder — populated only when transport = "sfu"
    sfu_room_id = models.CharField(max_length=100, null=True, blank=True)

    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "menntrix_channel_stream"
        indexes = [models.Index(fields=["channel", "started_at"])]

    def __str__(self):
        return f"stream {self.id} on {self.channel_id}"


# ============================================================
# CHANNEL SUBSCRIPTION
# ============================================================
class ChannelSubscription(models.Model):
    """A user subscribed to a channel — gets notified when they go live."""

    channel = models.ForeignKey(
        Channel, on_delete=models.CASCADE, related_name="subscriptions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menntrix_channel_subs",
    )
    subscribed_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    # Notification preference
    notify_on_live = models.BooleanField(default=True)

    class Meta:
        db_table = "menntrix_channel_subscription"
        unique_together = ("channel", "user")
        indexes = [
            models.Index(fields=["channel", "is_active"]),
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user_id} → #{self.channel.slug}"