import json
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages as flash
from django.conf import settings as dj_settings
from django.db import models
from django.db.models import Q
from django.utils import timezone
from .models import Channel, ChannelComment, ChannelStreamSession, ChannelSubscription
from .models import make_slug


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
# CHANNEL BROWSE
# ============================================================
@login_required
def channel_browse(request):
    q = request.GET.get("q", "").strip()
    qs = Channel.objects.filter(is_active=True).select_related("owner")
    if q:
        qs = qs.filter(
            Q(slug__icontains=q)
            | Q(title__icontains=q)
            | Q(owner__username__icontains=q)
        )
    qs = qs.order_by("-is_live", "-last_stream_at", "-created_at")[:200]
    return render(request, "menntrix/channel_browse.html", {"channels": qs, "q": q})


# ============================================================
# CHANNEL CREATE
# ============================================================
@login_required
def channel_create(request):
    if request.method == "POST":
        raw_name = (request.POST.get("slug") or "").strip().lower()
        title = (request.POST.get("title") or "").strip() or raw_name
        description = (request.POST.get("description") or "").strip()

        slug = make_slug(raw_name or request.user.username)
        if Channel.objects.filter(slug=slug).exists():
            flash.error(request, f"Channel @{slug} already taken.")
            return render(
                request,
                "menntrix/channel_create.html",
                {"slug": raw_name, "title": title},
            )

        ch = Channel.objects.create(
            slug=slug,
            owner=request.user,
            title=title,
            description=description,
        )
        _log(request.user, "channel_created", "channel", ch.slug,
             f"Created channel @{ch.slug}", request)
        flash.success(request, f"Channel @{slug} created.")
        return redirect("channel_watch", slug=ch.slug)

    return render(request, "menntrix/channel_create.html")


# ============================================================
# CHANNEL WATCH
# ============================================================
@login_required
def channel_watch(request, slug):
    ch = get_object_or_404(Channel, slug=slug)
    is_host = ch.owner_id == request.user.id

    # Increment view count (atomic)
    Channel.objects.filter(id=ch.id).update(view_count=models.F("view_count") + 1)
    ch.refresh_from_db()

    # Recent comments
    recent = (
        ChannelComment.objects
        .filter(channel=ch)
        .select_related("user")
        .order_by("-created_at")[:50]
    )
    recent = list(reversed(recent))

    recent_comments_json = json.dumps([
        {
            "id": c.id,
            "username": c.user.username,
            "text": c.text,
            "time": c.created_at.strftime("%H:%M"),
        }
        for c in recent
    ])

    # Subscription status
    is_subscribed = ChannelSubscription.objects.filter(
        channel=ch, user=request.user, is_active=True
    ).exists()

    # Avatars map for JS
    avatars = {}
    if ch.owner.profile_picture_menntrix:
        avatars[ch.owner_id] = ch.owner.profile_picture_menntrix
    if request.user.profile_picture_menntrix:
        avatars[request.user.id] = request.user.profile_picture_menntrix

    # Share URL
    share_url = reverse("share_link", args=["channel", ch.slug])

    return render(request, "menntrix/channel_watch.html", {
        "channel": ch,
        "is_host": is_host,
        "is_subscribed": is_subscribed,
        "ice_servers_json": json.dumps(dj_settings.MENNTRIX_ICE_SERVERS),
        "recent_comments_json": recent_comments_json,
        "avatars_json": json.dumps(avatars),
        "media_url": dj_settings.MEDIA_URL,
        "share_url": share_url,
    })


# ============================================================
# SUBSCRIBE / UNSUBSCRIBE
# ============================================================
@login_required
def channel_subscribe(request, slug):
    ch = get_object_or_404(Channel, slug=slug)

    sub, created = ChannelSubscription.objects.get_or_create(
        channel=ch,
        user=request.user,
        defaults={"is_active": True},
    )
    if not created and not sub.is_active:
        sub.is_active = True
        sub.save(update_fields=["is_active"])
        created = True

    if created:
        Channel.objects.filter(id=ch.id).update(
            subscriber_count=models.F("subscriber_count") + 1
        )
        _log(request.user, "channel_subscribed", "channel", ch.slug,
             f"Subscribed to @{ch.slug}", request)
        flash.success(request, f"Subscribed to @{ch.slug}.")

    return redirect("channel_watch", slug=slug)


@login_required
def channel_unsubscribe(request, slug):
    ch = get_object_or_404(Channel, slug=slug)

    removed = ChannelSubscription.objects.filter(
        channel=ch, user=request.user, is_active=True
    ).update(is_active=False)

    if removed:
        Channel.objects.filter(id=ch.id).update(
            subscriber_count=models.F("subscriber_count") - 1
        )
        _log(request.user, "channel_unsubscribed", "channel", ch.slug,
             f"Unsubscribed from @{ch.slug}", request)
        flash.success(request, f"Unsubscribed from @{ch.slug}.")

    return redirect("channel_watch", slug=slug)


# ============================================================
# GO LIVE
# ============================================================
@login_required
def channel_go_live(request, slug):
    ch = get_object_or_404(Channel, slug=slug, owner=request.user)

    if not ch.is_live:
        ChannelStreamSession.objects.create(
            channel=ch,
            host=request.user,
            transport="mesh",
        )
        ch.is_live = True
        ch.last_stream_at = timezone.now()
        ch.ended_at = None
        ch.save()

        # Broadcast live state to all WS viewers
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        if layer:
            async_to_sync(layer.group_send)(
                f"channel_{slug}",
                {"type": "stream.state", "state": "live"},
            )

        _log(request.user, "went_live", "channel", ch.slug,
             f"Went live on @{ch.slug}", request)
        flash.success(request, "You are now live.")

    return redirect("channel_watch", slug=slug)


# ============================================================
# END STREAM
# ============================================================
@login_required
def channel_end_stream(request, slug):
    ch = get_object_or_404(Channel, slug=slug, owner=request.user)

    if ch.is_live:
        # Log stream minutes for revenue tracking
        if ch.last_stream_at:
            try:
                minutes = int(
                    (timezone.now() - ch.last_stream_at).total_seconds() // 60
                )
                if minutes > 0:
                    from menntrix_revenue.usage import add_stream_minutes
                    add_stream_minutes(ch.owner, minutes)
            except Exception:
                pass

        ch.is_live = False
        ch.ended_at = timezone.now()
        ch.save()

        ChannelStreamSession.objects.filter(
            channel=ch, ended_at__isnull=True
        ).update(ended_at=timezone.now())

        # Broadcast ended state to all WS viewers
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        layer = get_channel_layer()
        if layer:
            async_to_sync(layer.group_send)(
                f"channel_{slug}",
                {"type": "stream.state", "state": "ended"},
            )

        _log(request.user, "stream_ended", "channel", ch.slug,
             f"Ended stream on @{ch.slug}", request)
        flash.success(request, "Stream ended.")

    return redirect("channel_watch", slug=slug)


# ============================================================
# MY CHANNELS
# ============================================================
@login_required
def channel_mine(request):
    owned = Channel.objects.filter(owner=request.user).order_by("-created_at")
    return render(request, "menntrix/channel_mine.html", {"channels": owned})