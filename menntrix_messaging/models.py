import os
import uuid

from django.db import models
from django.conf import settings


# ============================================================
# GROUP
# ============================================================

class Group(models.Model):
    """A saved group of MENNTRIX users for group messaging."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menntrix_groups_owned",
    )
    name = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "menntrix_group"

    def __str__(self):
        return self.name


class GroupMember(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menntrix_groups_joined",
    )
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "menntrix_group_member"
        unique_together = ("group", "user")


# ============================================================
# MESSAGE
# ============================================================

class Message(models.Model):
    """Email-style message between users (1-to-1, group, or multi-recipient)."""

    FOLDER_CHOICES = [
        ("inbox", "Inbox"),
        ("sent", "Sent"),
        ("drafts", "Drafts"),
        ("trash", "Trash"),
        ("starred", "Starred"),
    ]

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menntrix_messages_sent",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="menntrix_messages_received",
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
    )

    subject = models.CharField(max_length=255, blank=True, default="")
    body = models.TextField(blank=True, default="")

    folder = models.CharField(max_length=20, choices=FOLDER_CHOICES, default="inbox")

    is_read = models.BooleanField(default=False)
    is_starred = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "menntrix_message"
        indexes = [
            models.Index(fields=["recipient", "folder", "created_at"]),
            models.Index(fields=["sender", "folder", "created_at"]),
        ]

    def __str__(self):
        return f"#{self.id} {self.sender_id} → {self.recipient_id or self.group_id}"


class MessageRecipient(models.Model):
    """For multi-recipient messages (Cc-style fanout)."""

    message = models.ForeignKey(
        Message, on_delete=models.CASCADE, related_name="extra_recipients"
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menntrix_messages_cc",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "menntrix_message_recipient"
        unique_together = ("message", "recipient")


# ============================================================
# MESSAGE ATTACHMENT
# ============================================================

def attachment_upload_to(instance, filename):
    """Save to media/attachments/messages/<year>/<month>/<uuid>.<ext>"""
    from django.utils import timezone
    today = timezone.now()
    ext = os.path.splitext(filename)[1].lower()
    safe_name = f"{uuid.uuid4().hex[:12]}{ext}"
    return f"attachments/messages/{today.year}/{today.month:02d}/{safe_name}"


class MessageAttachment(models.Model):
    """A single attachment on a Message.

    Categories:
      - text  → `.text_content` is shown inline
      - link  → `.url` is opened
      - image → `.file` renders inline
      - video → `.file` renders inline
      - audio → `.file` renders inline
      - file  → `.file` gets a download link (ZIP goes here)
    """

    CATEGORY_CHOICES = [
        ("text", "Text"),
        ("link", "Link"),
        ("image", "Image"),
        ("video", "Video"),
        ("audio", "Audio"),
        ("file", "File / ZIP"),
    ]

    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name="attachments",
    )

    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)

    name = models.CharField(max_length=255, blank=True, default="")

    # For category="text"
    text_content = models.TextField(blank=True, default="")

    # For category="link"
    url = models.URLField(max_length=1000, blank=True, default="")

    # For image / video / audio / file
    file = models.FileField(
        upload_to=attachment_upload_to,
        blank=True,
        null=True,
    )

    # Metadata
    mime_type = models.CharField(max_length=120, blank=True, default="")
    file_size = models.BigIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "menntrix_message_attachment"
        ordering = ["id"]

    def __str__(self):
        return f"#{self.id} {self.category} → msg {self.message_id}"

    # ---- helpers for templates ----
    @property
    def is_image(self):
        return self.category == "image"

    @property
    def is_video(self):
        return self.category == "video"

    @property
    def is_audio(self):
        return self.category == "audio"

    @property
    def is_link(self):
        return self.category == "link"

    @property
    def is_text(self):
        return self.category == "text"

    @property
    def is_file(self):
        return self.category == "file"

    @property
    def size_display(self):
        n = self.file_size or 0
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} TB"

    def save(self, *args, **kwargs):
        # Auto-fill size + mime from the file
        if self.file and not self.file_size:
            try:
                self.file_size = self.file.size
            except Exception:
                pass
        if self.file and not self.mime_type:
            import mimetypes
            self.mime_type = mimetypes.guess_type(self.file.name)[0] or ""
        super().save(*args, **kwargs)