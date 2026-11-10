from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from .notifications import notify, log_activity
from .models import SecurityLog, UserLocation, UserPrivacy
from .location_utils import get_client_ip, lookup_ip


def _capture(user, request, source, event_type=None, severity="info"):
    """Write a UserLocation row and optionally a SecurityLog row."""
    ip = get_client_ip(request) if request else ""
    geo = lookup_ip(ip)
    ua = request.META.get("HTTP_USER_AGENT", "")[:500] if request else ""
    session_key = request.session.session_key if request and hasattr(request, "session") else None

    UserLocation.objects.create(
        user=user,
        session_key=session_key,
        ip_address=ip,
        ip_city=geo.get("city"),
        ip_region=geo.get("region"),
        ip_country=geo.get("country"),
        ip_isp=geo.get("isp"),
        user_agent=ua,
        source=source,
    )

    if event_type:
        SecurityLog.objects.create(
            user=user,
            event_type=event_type,
            severity=severity,
            ip_address=ip,
            details={
                "user_agent": ua,
                "country": geo.get("country"),
                "city": geo.get("city"),
            },
        )


@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    UserPrivacy.objects.get_or_create(user=user)

    ip = get_client_ip(request) if request else ""
    geo = lookup_ip(ip)
    country = geo.get("country") or ""

    # Check for new country
    prev = (
        UserLocation.objects
        .filter(user=user, source="login")
        .exclude(ip_country=country)
        .exclude(ip_country__isnull=True)
        .exclude(ip_country="")
        .order_by("-created_at")
        .first()
    )

    severity = "info"
    event_type = "login"
    if prev and prev.ip_country and country and prev.ip_country != country:
        severity = "warn"
        event_type = "new_country"

    _capture(user, request, source="login", event_type=event_type, severity=severity)


@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    if user:
        _capture(user, request, source="logout", event_type="logout", severity="info")

        # ============================================================
# ACTIVITY LOG + WELCOME EMAIL ON SIGNUP
# ============================================================

from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(user_logged_in)
def log_login_activity(sender, request, user, **kwargs):
    log_activity(
        user=user,
        action="login",
        description=f"Signed in from {request.META.get('REMOTE_ADDR', 'unknown') if request else 'unknown'}",
        request=request,
    )


@receiver(user_logged_out)
def log_logout_activity(sender, request, user, **kwargs):
    if user:
        log_activity(
            user=user,
            action="logout",
            description="Signed out",
            request=request,
        )