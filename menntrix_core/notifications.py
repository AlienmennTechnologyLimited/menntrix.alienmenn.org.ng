import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import Notification, ActivityLog, EmailConfig

log = logging.getLogger(__name__)


# ============================================================
# EMAIL HELPERS
# ============================================================

def get_from_email():
    try:
        cfg = EmailConfig.objects.filter(is_active=True).first()
        if cfg:
            return f"{cfg.from_name} <{cfg.from_email}>"
    except Exception:
        pass
    return getattr(settings, "DEFAULT_FROM_EMAIL", "team@alienmenn.org.ng")


def send_email(subject, to_email, template, context=None, reply_to=None):
    """Send an HTML email with a plain-text fallback."""
    context = context or {}
    context.setdefault("subject", subject)
    try:
        html = render_to_string(template, context)
        text = strip_tags(html)
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text,
            from_email=get_from_email(),
            to=[to_email],
            reply_to=reply_to or [],
        )
        msg.attach_alternative(html, "text/html")
        msg.send(fail_silently=True)
        return True
    except Exception as e:
        log.exception("Email send failed: %s", e)
        return False


# ============================================================
# NOTIFY — the master helper
# ============================================================

def notify(user, verb, title, body="", url="", actor=None, send_email_flag=True, send_push_flag=True):
    """
    Create an in-app Notification and (optionally) trigger email + push.
    Returns the Notification instance.
    """
    n = Notification.objects.create(
        user=user,
        actor=actor,
        verb=verb,
        title=title[:255],
        body=body,
        url=url,
    )

    # Email — check user's privacy flag
    if send_email_flag and _user_allows_email(user):
        ok = send_email(
            subject=f"[MENNTRIX] {title}",
            to_email=user.email,
            template="emails/notification.html",
            context={
                "user": user,
                "actor": actor,
                "verb": verb,
                "title": title,
                "body": body,
                "url": url,
            },
        )
        if ok:
            n.email_sent = True
            n.save(update_fields=["email_sent"])

    # Web push
    if send_push_flag:
        try:
            from .push import send_push
            ok = send_push(user, title=title, body=body, url=url)
            if ok:
                n.push_sent = True
                n.save(update_fields=["push_sent"])
        except Exception as e:
            log.warning("Push send failed: %s", e)

    return n


def _user_allows_email(user):
    """Check the user's privacy flag for email notifications."""
    try:
        privacy = user.menntrix_privacy
        return getattr(privacy, "allow_email_notifications", True)
    except Exception:
        return True


# ============================================================
# ACTIVITY LOG
# ============================================================

def log_activity(user, action, target_type="", target_id="", description="", request=None):
    ip = None
    if request is not None:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        ip = (xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", ""))
    return ActivityLog.objects.create(
        user=user,
        action=action,
        target_type=target_type,
        target_id=str(target_id or ""),
        description=description,
        ip_address=ip,
    )

    # ============================================================
# BROADCAST TO WEBSOCKET LISTENER
# ============================================================

def broadcast_to_user(user_id, event):
    """Send an event to the user's listener WebSocket group."""
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        if layer:
            async_to_sync(layer.group_send)(f"user_{user_id}", event)
    except Exception as e:
        log.warning("Broadcast to user failed: %s", e)