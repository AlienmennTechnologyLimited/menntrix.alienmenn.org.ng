import uuid
from django.db import models
from django.conf import settings


def make_uuid():
    return uuid.uuid4().hex


class Meeting(models.Model):
    """A group video meeting with a shareable UUID link."""

    uuid = models.CharField(max_length=32, primary_key=True, default=make_uuid, editable=False)
    host = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menntrix_meetings_hosted",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")

    is_active = models.BooleanField(default=True)
    is_locked = models.BooleanField(default=False)
    max_participants = models.IntegerField(default=6)

    scheduled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "menntrix_meeting"
        indexes = [
            models.Index(fields=["host", "created_at"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.uuid[:8]})"


class MeetingParticipant(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menntrix_meetings_joined",
    )
    is_host = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "menntrix_meeting_participant"
        unique_together = ("meeting", "user")
        indexes = [models.Index(fields=["meeting", "joined_at"])]


class MeetingMessage(models.Model):
    """In-meeting chat."""

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "menntrix_meeting_message"
        indexes = [models.Index(fields=["meeting", "created_at"])]


class MeetingLocation(models.Model):
    """Optional location shared during a meeting."""

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="locations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    accuracy_m = models.IntegerField(null=True, blank=True)
    shared_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "menntrix_meeting_location"
        indexes = [models.Index(fields=["meeting", "user", "shared_at"])]