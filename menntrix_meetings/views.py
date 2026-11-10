import json
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages as flash
from django.utils import timezone
from django.conf import settings as dj_settings
from .models import Meeting, MeetingParticipant


# ============================================================
# ACTIVITY LOG HELPER
# ============================================================

def _log(user, action, target_type="", target_id="", description="", request=None):
    """Safe activity log helper — never breaks the view."""
    try:
        from menntrix_core.notifications import log_activity
        log_activity(user, action, target_type, target_id, description, request)
    except Exception:
        pass


# ============================================================
# MEETING LIST
# ============================================================
@login_required
def meeting_list(request):
    hosted = Meeting.objects.filter(host=request.user).order_by("-created_at")[:50]
    joined = (
        Meeting.objects.filter(participants__user=request.user)
        .exclude(host=request.user)
        .distinct()
        .order_by("-created_at")[:50]
    )
    return render(request, "menntrix/meeting_list.html", {
        "hosted": hosted,
        "joined": joined,
    })


# ============================================================
# MEETING CREATE
# ============================================================
@login_required
def meeting_create(request):
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip() or "Untitled meeting"
        description = request.POST.get("description", "").strip()
        meeting = Meeting.objects.create(
            host=request.user,
            title=title,
            description=description,
            is_active=True,
        )
        _log(request.user, "meeting_created", "meeting", meeting.uuid,
             f"Created '{meeting.title}'", request)
        flash.success(request, "Meeting created. Share the link!")
        return redirect("meeting_room", uuid=meeting.uuid)
    return render(request, "menntrix/meeting_create.html")


# ============================================================
# MEETING ROOM
# ============================================================
@login_required
def meeting_room(request, uuid):
    meeting = get_object_or_404(Meeting, uuid=uuid)

    if not meeting.is_active:
        flash.error(request, "This meeting has ended.")
        return redirect("meeting_list")

    if meeting.is_locked and not MeetingParticipant.objects.filter(
        meeting=meeting, user=request.user
    ).exists():
        flash.error(request, "This meeting is locked.")
        return redirect("meeting_list")

    # Auto-register as participant
    MeetingParticipant.objects.get_or_create(
        meeting=meeting,
        user=request.user,
        defaults={"is_host": meeting.host_id == request.user.id},
    )

    meeting_link = request.build_absolute_uri(f"/meeting/{meeting.uuid}/")

    # Avatars map for JS
    avatars = {}
    for p in meeting.participants.select_related("user").all():
        if p.user.profile_picture_menntrix:
            avatars[p.user_id] = p.user.profile_picture_menntrix
    if request.user.profile_picture_menntrix:
        avatars[request.user.id] = request.user.profile_picture_menntrix
    if meeting.host.profile_picture_menntrix:
        avatars[meeting.host_id] = meeting.host.profile_picture_menntrix

    # Share URL
    share_url = reverse("share_link", args=["meeting", meeting.uuid])

    return render(request, "menntrix/meeting_room.html", {
        "meeting": meeting,
        "is_host": meeting.host_id == request.user.id,
        "ice_servers_json": json.dumps(dj_settings.MENNTRIX_ICE_SERVERS),
        "meeting_link": meeting_link,
        "avatars_json": json.dumps(avatars),
        "media_url": dj_settings.MEDIA_URL,
        "share_url": share_url,
    })


# ============================================================
# MEETING LEAVE
# ============================================================
@login_required
def meeting_leave(request, uuid):
    meeting = get_object_or_404(Meeting, uuid=uuid)
    MeetingParticipant.objects.filter(
        meeting=meeting, user=request.user, left_at__isnull=True
    ).update(left_at=timezone.now())
    return redirect("meeting_list")


# ============================================================
# MEETING END
# ============================================================
@login_required
def meeting_end(request, uuid):
    meeting = get_object_or_404(Meeting, uuid=uuid)
    if meeting.host_id != request.user.id:
        flash.error(request, "Only the host can end this meeting.")
        return redirect("meeting_room", uuid=uuid)

    meeting.is_active = False
    meeting.ended_at = timezone.now()
    meeting.save()

    MeetingParticipant.objects.filter(
        meeting=meeting, left_at__isnull=True
    ).update(left_at=timezone.now())

    # Broadcast meeting_ended to all WS peers
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer
    layer = get_channel_layer()
    if layer:
        async_to_sync(layer.group_send)(
            f"meeting_{uuid}",
            {"type": "meeting.ended", "sender_id": request.user.id},
        )

    _log(request.user, "meeting_ended", "meeting", meeting.uuid,
         f"Ended '{meeting.title}'", request)
    flash.success(request, "Meeting ended.")
    return redirect("meeting_list")


# ============================================================
# MEETING TOGGLE LOCK
# ============================================================
@login_required
def meeting_toggle_lock(request, uuid):
    meeting = get_object_or_404(Meeting, uuid=uuid)
    if meeting.host_id != request.user.id:
        return redirect("meeting_room", uuid=uuid)

    meeting.is_locked = not meeting.is_locked
    meeting.save()

    _log(request.user, "meeting_locked" if meeting.is_locked else "meeting_unlocked",
         "meeting", meeting.uuid,
         f"{'Locked' if meeting.is_locked else 'Unlocked'} '{meeting.title}'", request)

    flash.success(
        request,
        f"Meeting {'locked' if meeting.is_locked else 'unlocked'}.",
    )
    return redirect("meeting_room", uuid=uuid)