import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.http import JsonResponse
from .models import SecurityLog, UserLocation
from .location_utils import get_client_ip, lookup_ip
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Notification, ActivityLog, PushSubscription


# ============================================================
# CORE PAGES
# ============================================================

@login_required
def dashboard(request):
    recent_activity = (
        ActivityLog.objects
        .filter(user=request.user)
        .order_by("-created_at")[:5]
    )
    return render(request, "menntrix/dashboard.html", {
        "recent_activity": recent_activity,
    })


@login_required
def menu(request):
    return render(request, "menntrix/menu.html")


@login_required
def setting(request):
    return render(request, "menntrix/setting.html", {
        "profile_picture": getattr(request.user, "profile_picture_menntrix", "") or ""
    })


# ============================================================
# SETTINGS PAGES
# ============================================================

@login_required
def account(request):
    msg = {}
    if request.method == "POST":
        current = request.POST.get("currentpassword", "")
        if not request.user.check_password(current):
            msg["error_message"] = "Current password is incorrect."
        else:
            request.user.username = request.POST.get("username", request.user.username)
            request.user.planet = request.POST.get("planet", request.user.planet)
            request.user.save()
            msg["success_message"] = "Account updated."
    return render(request, "menntrix/account.html", msg)


@login_required
def personalinfo(request):
    msg = {}
    if request.method == "POST":
        current = request.POST.get("currentpassword", "")
        if not request.user.check_password(current):
            msg["error_message"] = "Current password is incorrect."
        else:
            u = request.user
            u.firstname = request.POST.get("firstname", u.firstname)
            u.middlename = request.POST.get("middlename", u.middlename)
            u.lastname = request.POST.get("lastname", u.lastname)
            u.mobile = request.POST.get("mobile", u.mobile)
            u.gender = request.POST.get("gender", u.gender)
            u.country = request.POST.get("country", u.country)
            u.save()
            msg["success_message"] = "Personal information updated."
    return render(request, "menntrix/personalinfo.html", msg)


@login_required
def payment(request):
    msg = {}
    if request.method == "POST":
        current = request.POST.get("currentpassword", "")
        if not request.user.check_password(current):
            msg["error_message"] = "Current password is incorrect."
        else:
            u = request.user
            u.bank_name = request.POST.get("bank_name", u.bank_name)
            u.bank_acc_name = request.POST.get("bank_acc_name", u.bank_acc_name)
            u.bank_acc_no = request.POST.get("bank_acc_no", u.bank_acc_no)
            u.bank_acc_type = request.POST.get("bank_acc_type", u.bank_acc_type)
            u.save()
            msg["success_message"] = "Payment information updated."
    return render(request, "menntrix/payment.html", msg)


@login_required
def security(request):
    msg = {}
    if request.method == "POST":
        current = request.POST.get("currentpassword", "")
        new = request.POST.get("newpassword", "")
        confirm = request.POST.get("confirmnewpassword", "")

        if not request.user.check_password(current):
            msg["error_message"] = "Current password is incorrect."
        elif new and new != confirm:
            msg["error_message"] = "New passwords do not match."
        elif new:
            request.user.set_password(new)
            request.user.save()
            update_session_auth_hash(request, request.user)

            # Security log entry
            SecurityLog.objects.create(
                user=request.user,
                event_type="password_change",
                severity="info",
                details={"by": "user"},
            )

            msg["success_message"] = "Password updated."
        else:
            msg["success_message"] = "No changes made."
    return render(request, "menntrix/security.html", msg)

@login_required
def profile_picture(request):
    msg = {}
    if request.method == "POST" and request.FILES.get("filename"):
        f = request.FILES["filename"]

        # Validate extension
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
            msg["error_message"] = "Only JPG, PNG, GIF, or WEBP allowed."
            return render(request, "menntrix/profile_picture.html", msg)

        # Save file with a safe unique name
        import uuid
        from django.core.files.storage import default_storage
        from django.core.files.base import ContentFile

        safe_name = f"user_{request.user.id}_{uuid.uuid4().hex[:8]}{ext}"
        default_storage.save(
            f"profile_pictures/{safe_name}",
            ContentFile(f.read()),
        )

        # Store just the filename in the model
        request.user.profile_picture_menntrix = safe_name
        request.user.save(update_fields=["profile_picture_menntrix"])

        msg["success_message"] = "Profile picture updated."

    return render(request, "menntrix/profile_picture.html", msg)

# ============================================================
# HEARTBEAT — location ping (15 min interval, client-driven)
# ============================================================

@login_required
def heartbeat(request):
    """Client posts lat/lng every 15 min if geolocation is granted."""
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required"}, status=405)

    lat = request.POST.get("lat")
    lng = request.POST.get("lng")
    acc = request.POST.get("accuracy")

    ip = get_client_ip(request)
    geo = lookup_ip(ip)
    ua = request.META.get("HTTP_USER_AGENT", "")[:500]

    accuracy_val = None
    if acc:
        try:
            accuracy_val = int(float(acc))
        except (ValueError, TypeError):
            accuracy_val = None

    UserLocation.objects.create(
        user=request.user,
        session_key=request.session.session_key,
        latitude=lat or None,
        longitude=lng or None,
        accuracy_m=accuracy_val,
        ip_address=ip,
        ip_city=geo.get("city"),
        ip_region=geo.get("region"),
        ip_country=geo.get("country"),
        ip_isp=geo.get("isp"),
        user_agent=ua,
        source="heartbeat",
    )
    return JsonResponse({"ok": True})

    # ============================================================
# NOTIFICATIONS
# ============================================================

@login_required
def notifications_page(request):
    qs = Notification.objects.filter(user=request.user).order_by("-created_at")[:200]
    return render(request, "menntrix/notifications.html", {"notifications": qs})


@login_required
def notifications_unread_count(request):
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({"count": count})


@login_required
def notifications_recent(request):
    qs = Notification.objects.filter(user=request.user).order_by("-created_at")[:10]
    data = []
    for n in qs:
        data.append({
            "id": n.id,
            "verb": n.verb,
            "title": n.title,
            "body": n.body,
            "url": n.url,
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat(),
        })
    return JsonResponse({"notifications": data})


@login_required
def notification_mark_read(request, notification_id):
    n = Notification.objects.filter(id=notification_id, user=request.user).first()
    if n:
        n.is_read = True
        n.save(update_fields=["is_read"])
    return redirect("notifications_page")


@login_required
def notifications_mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect("notifications_page")


# ============================================================
# ACTIVITY LOG
# ============================================================

@login_required
def activity_log_page(request):
    filter_type = request.GET.get("filter", "all")

    qs = ActivityLog.objects.filter(user=request.user).order_by("-created_at")

    if filter_type == "messages":
        qs = qs.filter(action__in=[
            "message_sent", "draft_saved", "trash_empty",
            "group_created", "group_deleted",
            "group_member_added", "group_member_removed",
            "group_renamed", "group_left",
        ])
    elif filter_type == "calls":
        qs = qs.filter(action__startswith="call_")
    elif filter_type == "meetings":
        qs = qs.filter(action__startswith="meeting_")
    elif filter_type == "channels":
        qs = qs.filter(action__in=["went_live", "stream_ended"])
    elif filter_type == "connections":
        qs = qs.filter(action__in=[
            "connection_added", "connection_removed",
            "block_added", "block_removed",
        ])
    elif filter_type == "auth":
        qs = qs.filter(action__in=["login", "logout", "signup"])

    qs = qs[:200]

    return render(request, "menntrix/activity_log.html", {
        "activities": qs,
        "filter_type": filter_type,
    })


# ============================================================
# PUSH SUBSCRIPTION ENDPOINTS
# ============================================================

@login_required
def push_public_key(request):
    from .push import get_public_key
    return JsonResponse({"publicKey": get_public_key()})


@login_required
def push_subscribe(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required"}, status=405)

    import json
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    endpoint = data.get("endpoint")
    keys = data.get("keys") or {}
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")

    if not (endpoint and p256dh and auth):
        return JsonResponse({"ok": False, "error": "missing fields"}, status=400)

    sub, created = PushSubscription.objects.update_or_create(
        user=request.user,
        endpoint=endpoint,
        defaults={
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
            "is_active": True,
        },
    )
    return JsonResponse({"ok": True, "created": created})


@login_required
def push_unsubscribe(request):
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)
    import json
    try:
        data = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False}, status=400)
    endpoint = data.get("endpoint")
    if endpoint:
        PushSubscription.objects.filter(user=request.user, endpoint=endpoint).update(is_active=False)
    return JsonResponse({"ok": True})

    # ============================================================
# SHARE LINKS
# ============================================================
@login_required
def share_link(request, kind, pk):
    """
    Return shareable info for a channel, meeting, call, or user profile.
    GET /share/channel/alienmenn/
    GET /share/meeting/<uuid>/
    GET /share/call/<call_id>/
    GET /share/profile/<user_id>/
    """
    from django.urls import reverse
    from menntrix_channels.models import Channel
    from menntrix_meetings.models import Meeting
    from menntrix_calls.models import CallSession
    from menntrix_accounts.models import UserAccount

    url_path = None
    title = ""
    subtitle = ""

    if kind == "channel":
        c = get_object_or_404(Channel, slug=pk)
        url_path = reverse("channel_watch", args=[c.slug])
        title = c.title
        subtitle = f"@{c.slug} · MENNTRIX Channel"

    elif kind == "meeting":
        m = get_object_or_404(Meeting, uuid=pk)
        url_path = reverse("meeting_room", args=[m.uuid])
        title = m.title
        subtitle = f"Meeting with {m.host.username}"

    elif kind == "call":
        s = get_object_or_404(CallSession, call_id=pk)
        if request.user.id not in (s.caller_id, s.callee_id):
            return JsonResponse({"ok": False}, status=403)
        url_path = reverse("call_room", args=[s.call_id])
        title = "Join call"
        peer = s.callee if s.caller_id == request.user.id else s.caller
        subtitle = f"Call with @{peer.username}"

    elif kind == "profile":
        u = get_object_or_404(UserAccount, id=pk)
        url_path = reverse("profile_view", args=[u.id])
        title = f"{u.firstname} {u.lastname}".strip() or u.username
        subtitle = f"@{u.username} · MENNTRIX"

    else:
        return JsonResponse({"ok": False, "error": "unknown kind"}, status=400)

    full_url = request.build_absolute_uri(url_path)

    return render(request, "menntrix/share_card.html", {
        "kind": kind,
        "pk": pk,
        "url": full_url,
        "title": title,
        "subtitle": subtitle,
    })