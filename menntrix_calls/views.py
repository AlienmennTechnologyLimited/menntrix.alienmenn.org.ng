import json
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings as dj_settings
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from menntrix_accounts.models import UserAccount
from menntrix_connections.models import Connection, Block
from .models import CallSession


# ============================================================
# ACTIVITY LOG HELPER
# ============================================================

def _log(user, action, target_type="", target_id="", description="", request=None):
    """Safe activity log helper - never breaks the view."""
    try:
        from menntrix_core.notifications import log_activity
        log_activity(user, action, target_type, target_id, description, request)
    except Exception:
        pass


# ============================================================
# POLICY CONSTANTS
# ============================================================

RING_TIMEOUT_SECONDS = 60
HEARTBEAT_TIMEOUT_SECONDS = 90


# ============================================================
# HELPERS
# ============================================================

def _broadcast_to_user(user_id, event):
    layer = get_channel_layer()
    if not layer:
        return
    async_to_sync(layer.group_send)(f"user_{user_id}", event)


def _broadcast_to_call(call_id, event):
    layer = get_channel_layer()
    if not layer:
        return
    async_to_sync(layer.group_send)(f"call_{call_id}", event)


def _expire_stale_calls():
    now = timezone.now()

    ring_cutoff = now - timedelta(seconds=RING_TIMEOUT_SECONDS)
    CallSession.objects.filter(
        status="ringing",
        started_at__lt=ring_cutoff,
    ).update(status="missed", ended_at=now, ended_reason="ring_timeout")

    hb_cutoff = now - timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS)
    CallSession.objects.filter(
        status="active",
    ).filter(
        Q(last_heartbeat__lt=hb_cutoff) | Q(last_heartbeat__isnull=True)
    ).update(status="ended", ended_at=now, ended_reason="heartbeat_timeout")


def _user_busy(user_id):
    _expire_stale_calls()
    now = timezone.now()

    hb_cutoff = now - timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS)
    active = CallSession.objects.filter(
        Q(caller_id=user_id) | Q(callee_id=user_id),
        status="active",
    ).filter(
        Q(last_heartbeat__gte=hb_cutoff)
        | Q(last_heartbeat__isnull=True, answered_at__gte=hb_cutoff)
    ).exists()
    if active:
        return True

    ring_cutoff = now - timedelta(seconds=RING_TIMEOUT_SECONDS)
    return CallSession.objects.filter(
        Q(caller_id=user_id) | Q(callee_id=user_id),
        status="ringing",
        started_at__gte=ring_cutoff,
    ).exists()


def _caller_can_call(caller, callee):
    if Block.objects.filter(user=callee, blocked=caller).exists():
        return False, "blocked"
    if Block.objects.filter(user=caller, blocked=callee).exists():
        return False, "blocked"

    try:
        privacy = callee.menntrix_privacy
    except Exception:
        privacy = None

    if privacy and privacy.only_connections_can_call:
        if not Connection.objects.filter(user=callee, peer=caller).exists():
            return False, "forbidden"

    return True, "ok"


# ============================================================
# VIEWS
# ============================================================

@login_required
def call_start(request, user_id, call_type="video"):
    _expire_stale_calls()

    if call_type not in ("voice", "video"):
        call_type = "video"

    is_ajax = (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or request.headers.get("accept", "").startswith("application/json")
    )

    callee = get_object_or_404(UserAccount, id=user_id)

    def _err(reason):
        if is_ajax:
            return JsonResponse({"ok": False, "reason": reason}, status=403)
        from django.contrib import messages as flash
        flash.error(request, {
            "self": "You can't call yourself.",
            "busy": "User is busy or unavailable.",
            "blocked": "You can't call this user.",
            "forbidden": "You're not allowed to call this user.",
        }.get(reason, "Unable to start call."))
        return redirect(request.META.get("HTTP_REFERER") or "dashboard")

    if callee.id == request.user.id:
        return _err("self")

    allowed, reason = _caller_can_call(request.user, callee)
    if not allowed:
        return _err(reason)

    if _user_busy(callee.id):
        return _err("busy")

    if _user_busy(request.user.id):
        return _err("busy")

    session = CallSession.objects.create(
        caller=request.user,
        callee=callee,
        call_type=call_type,
        status="ringing",
        last_heartbeat=timezone.now(),
    )

    caller_avatar = request.user.profile_picture_menntrix or ""
    caller_name = (
        (request.user.firstname or "") + " " + (request.user.lastname or "")
    ).strip() or request.user.username

    _broadcast_to_user(callee.id, {
        "type": "incoming_call",
        "call_id": session.call_id,
        "caller_id": request.user.id,
        "caller_username": request.user.username,
        "caller_name": caller_name,
        "caller_avatar": caller_avatar,
        "call_type": call_type,
        "url": f"/call/{session.call_id}/",
    })

    _log(
        request.user,
        "call_started",
        "call",
        session.call_id,
        f"{call_type.title()} call with {callee.username}",
        request,
    )

    if is_ajax:
        return JsonResponse({
            "ok": True,
            "call_id": session.call_id,
            "status": "ringing",
            "url": f"/call/{session.call_id}/",
        })

    return redirect("call_room", call_id=session.call_id)


@login_required
def call_room(request, call_id):
    session = get_object_or_404(CallSession, call_id=call_id)

    if request.user.id not in (session.caller_id, session.callee_id):
        return redirect("dashboard")

    if session.status in ("ended", "missed", "rejected"):
        from django.contrib import messages as flash
        flash.error(request, "This call has ended.")
        return redirect("call_history")

    if session.status == "ringing" and request.user.id == session.callee_id:
        session.status = "active"
        session.answered_at = timezone.now()
        session.last_heartbeat = timezone.now()
        session.save()
    elif session.status == "active":
        session.last_heartbeat = timezone.now()
        session.save(update_fields=["last_heartbeat"])

    peer = session.callee if request.user.id == session.caller_id else session.caller

    avatars = {}
    if request.user.profile_picture_menntrix:
        avatars[request.user.id] = request.user.profile_picture_menntrix
    if peer.profile_picture_menntrix:
        avatars[peer.id] = peer.profile_picture_menntrix

    peer_share_url = reverse("share_link", args=["profile", peer.id])

    return render(request, "menntrix/call_room.html", {
        "session": session,
        "peer": peer,
        "ice_servers_json": json.dumps(dj_settings.MENNTRIX_ICE_SERVERS),
        "avatars_json": json.dumps(avatars),
        "media_url": dj_settings.MEDIA_URL,
        "peer_share_url": peer_share_url,
        "is_caller": request.user.id == session.caller_id,
    })


@login_required
def call_ping(request, call_id):
    session = CallSession.objects.filter(call_id=call_id).first()
    if not session:
        return JsonResponse({"ok": False}, status=404)
    if request.user.id not in (session.caller_id, session.callee_id):
        return JsonResponse({"ok": False}, status=403)

    session.last_heartbeat = timezone.now()
    session.save(update_fields=["last_heartbeat"])
    return JsonResponse({"ok": True, "status": session.status})


@login_required
def call_status(request, call_id):
    _expire_stale_calls()

    session = CallSession.objects.filter(call_id=call_id).first()
    if not session:
        return JsonResponse({"status": "missing"}, status=404)
    if request.user.id not in (session.caller_id, session.callee_id):
        return JsonResponse({"status": "forbidden"}, status=403)

    return JsonResponse({"status": session.status})


@login_required
def call_accept(request, call_id):
    session = get_object_or_404(CallSession, call_id=call_id)
    if request.user.id != session.callee_id:
        return redirect("dashboard")

    if session.status == "ringing":
        session.status = "active"
        session.answered_at = timezone.now()
        session.last_heartbeat = timezone.now()
        session.save()

        _broadcast_to_user(session.caller_id, {
            "type": "call_accepted",
            "call_id": session.call_id,
            "url": f"/call/{session.call_id}/",
        })

    return redirect("call_room", call_id=session.call_id)


@login_required
def call_reject(request, call_id):
    session = get_object_or_404(CallSession, call_id=call_id)
    if request.user.id != session.callee_id:
        return JsonResponse({"ok": False}, status=403)

    if session.status == "ringing":
        session.status = "rejected"
        session.ended_at = timezone.now()
        session.ended_reason = "rejected"
        session.save()

        _broadcast_to_user(session.caller_id, {
            "type": "call_rejected",
            "call_id": session.call_id,
        })

    return JsonResponse({"ok": True})


@login_required
def call_cancel(request, call_id):
    session = get_object_or_404(CallSession, call_id=call_id)
    if request.user.id != session.caller_id:
        return JsonResponse({"ok": False}, status=403)

    if session.status == "ringing":
        session.status = "ended"
        session.ended_at = timezone.now()
        session.ended_reason = "cancelled"
        session.save()

        _broadcast_to_user(session.callee_id, {
            "type": "call_cancelled",
            "call_id": session.call_id,
        })

    return JsonResponse({"ok": True})


@login_required
def call_end(request, call_id):
    session = get_object_or_404(CallSession, call_id=call_id)
    if request.user.id in (session.caller_id, session.callee_id):
        if session.status != "ended":
            session.status = "ended"
            session.ended_at = timezone.now()
            session.ended_reason = "user_hung_up"
            if session.answered_at:
                session.duration_sec = int((session.ended_at - session.answered_at).total_seconds())
            session.save()

            # Revenue: log call minutes for both peers
            try:
                if session.answered_at:
                    minutes = int((session.ended_at - session.answered_at).total_seconds() // 60)
                    if minutes > 0:
                        from menntrix_revenue.usage import add_call_minutes
                        add_call_minutes(session.caller, minutes)
                        add_call_minutes(session.callee, minutes)
            except Exception:
                pass

            # Notify BOTH users' global listeners to redirect instantly
            _broadcast_to_user(session.caller_id, {
                "type": "call_ended",
                "call_id": session.call_id,
            })
            _broadcast_to_user(session.callee_id, {
                "type": "call_ended",
                "call_id": session.call_id,
            })
            
            # Notify the call room to cleanup UI
            _broadcast_to_call(session.call_id, {
                "type": "call.ended",
                "sender_id": request.user.id,
            })
            
    return redirect("dashboard")


@login_required
def call_end_ajax(request, call_id):
    session = CallSession.objects.filter(call_id=call_id).first()
    if not session:
        return JsonResponse({"ok": False}, status=404)
    if request.user.id not in (session.caller_id, session.callee_id):
        return JsonResponse({"ok": False}, status=403)

    if session.status != "ended":
        session.status = "ended"
        session.ended_at = timezone.now()
        session.ended_reason = "peer_disconnected"
        if session.answered_at:
            session.duration_sec = int((session.ended_at - session.answered_at).total_seconds())
        session.save()

        try:
            if session.answered_at:
                minutes = int((session.ended_at - session.answered_at).total_seconds() // 60)
                if minutes > 0:
                    from menntrix_revenue.usage import add_call_minutes
                    add_call_minutes(session.caller, minutes)
                    add_call_minutes(session.callee, minutes)
        except Exception:
            pass

        # Notify BOTH users' global listeners to redirect instantly
        _broadcast_to_user(session.caller_id, {
            "type": "call_ended",
            "call_id": session.call_id,
        })
        _broadcast_to_user(session.callee_id, {
            "type": "call_ended",
            "call_id": session.call_id,
        })
        
        # Notify the call room to cleanup UI
        _broadcast_to_call(session.call_id, {
            "type": "call.ended",
            "sender_id": request.user.id,
        })

    return JsonResponse({"ok": True})


@login_required
def call_clear_mine(request):
    _expire_stale_calls()

    cleared = CallSession.objects.filter(
        Q(caller=request.user) | Q(callee=request.user),
        status__in=["ringing", "active"],
    ).update(
        status="ended",
        ended_at=timezone.now(),
        ended_reason="system",
    )

    from django.contrib import messages as flash
    flash.success(request, f"Cleared {cleared} stuck call(s).")
    return redirect("call_history")


@login_required
def call_history(request):
    made = CallSession.objects.filter(caller=request.user).order_by("-started_at")[:50]
    received = CallSession.objects.filter(callee=request.user).order_by("-started_at")[:50]
    return render(request, "menntrix/call_history.html", {"made": made, "received": received})