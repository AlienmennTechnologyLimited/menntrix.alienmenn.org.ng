from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib import messages as flash
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.template.loader import render_to_string
from menntrix_accounts.models import UserAccount
from .models import Connection, Block, Report


PAGE_SIZE = 20


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
# PEOPLE SEARCH
# ============================================================

@login_required
def people_search(request):
    """Search anyone on the platform (excluding blocked)."""
    q = request.GET.get("q", "").strip()

    blocked_ids = list(
        Block.objects.filter(user=request.user).values_list("blocked_id", flat=True)
    ) + list(
        Block.objects.filter(blocked=request.user).values_list("user_id", flat=True)
    )

    users = UserAccount.objects.exclude(id=request.user.id).exclude(id__in=blocked_ids)

    if q:
        users = users.filter(
            Q(username__icontains=q)
            | Q(firstname__icontains=q)
            | Q(lastname__icontains=q)
            | Q(email__icontains=q)
            | Q(country__icontains=q)
        )

    users = users.order_by("-id")

    paginator = Paginator(users, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    connected_ids = set(
        Connection.objects.filter(user=request.user).values_list("peer_id", flat=True)
    )

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        html = render_to_string(
            "menntrix/_people_rows.html",
            {"users": page_obj, "connected_ids": connected_ids, "q": q},
            request=request,
        )
        return JsonResponse({
            "html": html,
            "has_next": page_obj.has_next(),
            "next_page": page_obj.next_page_number() if page_obj.has_next() else None,
        })

    return render(request, "menntrix/people.html", {
        "users": page_obj,
        "connected_ids": connected_ids,
        "q": q,
    })


# ============================================================
# NEW MEMBERS
# ============================================================

@login_required
def new_members(request):
    """People who joined recently."""
    blocked_ids = list(
        Block.objects.filter(user=request.user).values_list("blocked_id", flat=True)
    )

    users = (
        UserAccount.objects.exclude(id=request.user.id)
        .exclude(id__in=blocked_ids)
        .order_by("-id")[:50]
    )

    connected_ids = set(
        Connection.objects.filter(user=request.user).values_list("peer_id", flat=True)
    )

    return render(request, "menntrix/new_members.html", {
        "users": users,
        "connected_ids": connected_ids,
    })


# ============================================================
# CONNECTIONS LIST
# ============================================================

@login_required
def connection_list(request):
    """Your saved connections."""
    connections = (
        Connection.objects.filter(user=request.user)
        .select_related("peer")
        .order_by("-created_at")
    )

    peers = [c.peer for c in connections]

    return render(request, "menntrix/connections.html", {
        "peers": peers,
        "connected_ids": set(p.id for p in peers),
    })


# ============================================================
# CONNECT / DISCONNECT
# ============================================================

@login_required
def connection_add(request, user_id):
    peer = get_object_or_404(UserAccount, id=user_id)

    if peer.id == request.user.id:
        return redirect("people_search")

    conn, created = Connection.objects.get_or_create(user=request.user, peer=peer)

    if created:
        _log(
            request.user,
            "connection_added",
            "user",
            peer.id,
            f"Connected with {peer.username}",
            request,
        )
        flash.success(request, f"{peer.username} added to your connections.")
    else:
        flash.success(request, f"{peer.username} is already in your connections.")

    next_url = request.GET.get("next") or request.META.get("HTTP_REFERER") or "/people/"
    return redirect(next_url)


@login_required
def connection_remove(request, user_id):
    peer = UserAccount.objects.filter(id=user_id).first()
    removed, _ = Connection.objects.filter(user=request.user, peer_id=user_id).delete()

    if removed and peer:
        _log(
            request.user,
            "connection_removed",
            "user",
            peer.id,
            f"Removed connection with {peer.username}",
            request,
        )

    flash.success(request, "Connection removed.")
    next_url = request.GET.get("next") or request.META.get("HTTP_REFERER") or "/connections/"
    return redirect(next_url)


# ============================================================
# PROFILE VIEW
# ============================================================

@login_required
def profile_view(request, user_id):
    """View any user's public profile."""
    profile_user = get_object_or_404(UserAccount, id=user_id)
    is_connected = Connection.objects.filter(user=request.user, peer=profile_user).exists()
    is_self = profile_user.id == request.user.id

    return render(request, "menntrix/profile_view.html", {
        "profile_user": profile_user,
        "is_connected": is_connected,
        "is_self": is_self,
    })


# ============================================================
# BLOCK USER
# ============================================================

@login_required
def block_user(request, user_id):
    peer = get_object_or_404(UserAccount, id=user_id)

    if peer.id == request.user.id:
        return redirect("people_search")

    block, created = Block.objects.get_or_create(user=request.user, blocked=peer)

    if created:
        # Remove any connection between the two users
        Connection.objects.filter(user=request.user, peer=peer).delete()
        Connection.objects.filter(user=peer, peer=request.user).delete()

        _log(
            request.user,
            "block_added",
            "user",
            peer.id,
            f"Blocked {peer.username}",
            request,
        )
        flash.success(request, f"{peer.username} blocked.")
    else:
        flash.success(request, f"{peer.username} is already blocked.")

    return redirect("people_search")


# ============================================================
# REPORT USER
# ============================================================

@login_required
def report_user(request, user_id):
    peer = get_object_or_404(UserAccount, id=user_id)
    reason = request.GET.get("reason", "Reported by user")

    if request.method == "POST":
        reason = request.POST.get("reason", reason)
        Report.objects.create(reporter=request.user, reported=peer, reason=reason)

        _log(
            request.user,
            "user_reported",
            "user",
            peer.id,
            f"Reported {peer.username}",
            request,
        )
        flash.success(request, "Report submitted. Thank you.")
        return redirect("people_search")

    return render(request, "menntrix/report_user.html", {"peer": peer})