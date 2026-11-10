import uuid
from django.db import models
from django.conf import settings


def make_call_id():
    return str(uuid.uuid4())


class CallSession(models.Model):
    """A single 1-to-1 call session."""

    CALL_TYPE_CHOICES = [
        ("voice", "Voice"),
        ("video", "Video"),
    ]
    STATUS_CHOICES = [
        ("ringing", "Ringing"),
        ("active", "Active"),
        ("ended", "Ended"),
        ("missed", "Missed"),
        ("rejected", "Rejected"),
    ]
    END_REASON_CHOICES = [
        ("", "—"),
        ("user_hung_up", "User hung up"),
        ("peer_disconnected", "Peer disconnected"),
        ("ring_timeout", "No answer"),
        ("heartbeat_timeout", "Connection lost"),
        ("cancelled", "Caller cancelled"),
        ("rejected", "Rejected"),
        ("busy", "Busy"),
        ("system", "System"),
    ]

    call_id = models.CharField(
        max_length=64,
        primary_key=True,
        default=make_call_id,
        editable=False,
    )
    caller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menntrix_calls_made",
    )
    callee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menntrix_calls_received",
    )
    call_type = models.CharField(max_length=10, choices=CALL_TYPE_CHOICES, default="video")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ringing")
    ended_reason = models.CharField(
        max_length=30, choices=END_REASON_CHOICES, blank=True, default=""
    )

    started_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_sec = models.IntegerField(default=0)

    # Heartbeat — updated by both peers every 30s while in the call room
    last_heartbeat = models.DateTimeField(null=True, blank=True)

    # Location sharing opt-in per call
    caller_share_location = models.BooleanField(default=False)
    callee_share_location = models.BooleanField(default=False)

    class Meta:
        db_table = "menntrix_call_session"
        indexes = [
            models.Index(fields=["caller", "started_at"]),
            models.Index(fields=["callee", "started_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.call_id} {self.caller_id}->{self.callee_id} ({self.status})"


class CallSignal(models.Model):
    """WebRTC signaling messages — SDP offers/answers and ICE candidates."""

    SIGNAL_CHOICES = [
        ("offer", "Offer"),
        ("answer", "Answer"),
        ("ice", "ICE"),
    ]

    call = models.ForeignKey(
        CallSession, on_delete=models.CASCADE, related_name="signals"
    )
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    signal_type = models.CharField(max_length=10, choices=SIGNAL_CHOICES)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "menntrix_call_signal"
        indexes = [models.Index(fields=["call", "created_at"])]


class CallLocation(models.Model):
    """Location points shared during a call (opt-in per peer)."""

    call = models.ForeignKey(
        CallSession, on_delete=models.CASCADE, related_name="locations"
    )
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    accuracy_m = models.IntegerField(null=True, blank=True)
    shared_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "menntrix_call_location"
        indexes = [models.Index(fields=["call", "user", "shared_at"])]


class CallMessage(models.Model):
    """In-call text chat."""

    call = models.ForeignKey(
        CallSession, on_delete=models.CASCADE, related_name="messages"
    )
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "menntrix_call_message"
        indexes = [models.Index(fields=["call", "created_at"])]