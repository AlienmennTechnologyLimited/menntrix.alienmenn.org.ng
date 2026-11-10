from django.db import models
from django.conf import settings


class Connection(models.Model):
    """A bookmark-style connection between two MENNTRIX users."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="connections_sent",
    )
    peer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="connections_received",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "menntrix_connection"
        unique_together = ("user", "peer")
        indexes = [
            models.Index(fields=["user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.user_id} -> {self.peer_id}"


class Block(models.Model):
    """A user blocking another user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocks_sent",
    )
    blocked = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocks_received",
    )
    reason = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "menntrix_block"
        unique_together = ("user", "blocked")

    def __str__(self):
        return f"{self.user_id} blocked {self.blocked_id}"


class Report(models.Model):
    """A user reporting another user for review."""

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports_sent",
    )
    reported = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports_received",
    )
    reason = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "menntrix_report"

    def __str__(self):
        return f"{self.reporter_id} reported {self.reported_id}"