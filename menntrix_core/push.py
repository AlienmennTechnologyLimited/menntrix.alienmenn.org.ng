import json
import logging
import os

from django.conf import settings

log = logging.getLogger(__name__)


def _vapid_claims():
    email = os.getenv("VAPID_EMAIL", "mailto:team@alienmenn.org.ng")
    return {"sub": email}


def _vapid_private_key():
    return os.getenv("VAPID_PRIVATE_KEY", "")


def _vapid_public_key():
    return os.getenv("VAPID_PUBLIC_KEY", "")


def send_push(user, title, body="", url="", icon="/static/images/logo.gif"):
    """
    Send a Web Push notification to every active subscription of a user.
    Returns True if at least one push was delivered.
    """
    try:
        from pywebpush import webpush, WebPushException
    except Exception:
        log.warning("pywebpush not installed, skipping push")
        return False

    from .models import PushSubscription

    subs = PushSubscription.objects.filter(user=user, is_active=True)
    if not subs.exists():
        return False

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url,
        "icon": icon,
    })

    private_key = _vapid_private_key()
    if not private_key:
        log.warning("VAPID_PRIVATE_KEY missing; push skipped")
        return False

    delivered = False

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=private_key,
                vapid_claims=_vapid_claims(),
            )
            delivered = True
        except Exception as e:
            # If subscription is gone (410), mark inactive
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (404, 410):
                sub.is_active = False
                sub.save(update_fields=["is_active"])
            log.warning("Push to sub %s failed: %s", sub.id, e)

    return delivered


def get_public_key():
    return _vapid_public_key()