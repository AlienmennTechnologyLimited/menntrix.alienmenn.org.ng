from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages as flash
from django.conf import settings as dj_settings
from django.utils import timezone
from .models import UserLocation, SecurityLog, UserPrivacy
from menntrix_connections.models import Block


@login_required
def privacy_page(request):
    privacy, _ = UserPrivacy.objects.get_or_create(user=request.user)

    if request.method == "POST":
        privacy.share_location_calls = bool(request.POST.get("share_location_calls"))
        privacy.share_location_meetings = bool(request.POST.get("share_location_meetings"))
        privacy.share_location_channels = bool(request.POST.get("share_location_channels"))
        privacy.allow_location_history = bool(request.POST.get("allow_location_history"))
        privacy.only_connections_can_call = bool(request.POST.get("only_connections_can_call"))
        privacy.only_connections_can_message = bool(request.POST.get("only_connections_can_message"))
        privacy.save()
        flash.success(request, "Privacy settings updated.")

    return render(request, "menntrix/privacy.html", {
        "privacy": privacy,
        "ice_servers": dj_settings.MENNTRIX_ICE_SERVERS,
    })


@login_required
def privacy_location(request):
    entries = (
        UserLocation.objects
        .filter(user=request.user, latitude__isnull=False, longitude__isnull=False)
        .order_by("-created_at")[:50]
    )
    return render(request, "menntrix/privacy_location.html", {
        "entries": entries,
        "google_maps_key": "AIzaSyDUMMY_REPLACE_WITH_REAL_KEY",
    })


@login_required
def privacy_security(request):
    events = SecurityLog.objects.filter(user=request.user).order_by("-created_at")[:200]
    return render(request, "menntrix/privacy_security.html", {"events": events})


@login_required
def privacy_clear_location(request):
    if request.method == "POST":
        UserLocation.objects.filter(user=request.user).delete()
        SecurityLog.objects.create(
            user=request.user,
            event_type="location_cleared",
            severity="info",
            details={"by": "user"},
        )
        flash.success(request, "Location history cleared.")
    return redirect("privacy_location")


@login_required
def privacy_blocked(request):
    blocked = (
        Block.objects
        .filter(user=request.user)
        .select_related("blocked")
        .order_by("-created_at")
    )
    return render(request, "menntrix/privacy_blocked.html", {"blocked": blocked})


@login_required
def privacy_unblock(request, user_id):
    Block.objects.filter(user=request.user, blocked_id=user_id).delete()
    flash.success(request, "User unblocked.")
    return redirect("privacy_blocked")