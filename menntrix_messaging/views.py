import os
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages as flash
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.db.models import Q
from menntrix_accounts.models import UserAccount
from .models import Message, Group, GroupMember, MessageRecipient


PAGE_SIZE = 20


# ============================================================
# ATTACHMENT HELPERS
# ============================================================

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}
VIDEO_EXTS = {".mp4", ".webm", ".mov", ".m4v", ".avi", ".mkv"}
AUDIO_EXTS = {".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac"}


def _category_from_filename(name):
    ext = os.path.splitext(name)[1].lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    return "file"


def _save_attachments(message, files, links, texts):
    """Save all attachment kinds attached to a compose submission."""
    from .models import MessageAttachment

    for f in files:
        category = _category_from_filename(f.name)
        att = MessageAttachment(
            message=message,
            category=category,
            name=f.name,
            file=f,
        )
        att.save()

    for url in links:
        url = (url or "").strip()
        if url:
            MessageAttachment.objects.create(
                message=message,
                category="link",
                url=url,
                name=url[:120],
            )

    for t in texts:
        t = (t or "").strip()
        if t:
            MessageAttachment.objects.create(
                message=message,
                category="text",
                text_content=t,
                name="Text snippet",
            )


def _copy_attachments(src_message, dst_message):
    """Copy attachments from one message to another (sent ↔ inbox pairs)."""
    from .models import MessageAttachment
    for att in src_message.attachments.all():
        MessageAttachment.objects.create(
            message=dst_message,
            category=att.category,
            name=att.name,
            text_content=att.text_content,
            url=att.url,
            file=att.file,
            mime_type=att.mime_type,
            file_size=att.file_size,
        )


def _log(user, action, target_type="", target_id="", description="", request=None):
    """Safe activity log helper."""
    try:
        from menntrix_core.notifications import log_activity
        log_activity(user, action, target_type, target_id, description, request)
    except Exception:
        pass


# ============================================================
# QUERYSET HELPERS
# ============================================================

def _folder_qs(user, folder):
    """Return the queryset for a given folder."""
    base = Message.objects.select_related("sender", "recipient", "group")

    if folder == "sent":
        return base.filter(sender=user, folder="sent", is_deleted=False).order_by("-created_at")

    if folder == "drafts":
        return base.filter(sender=user, folder="drafts", is_deleted=False).order_by("-updated_at")

    if folder == "trash":
        return base.filter(
            Q(recipient=user) | Q(sender=user),
            is_deleted=True,
        ).order_by("-updated_at")

    if folder == "starred":
        return base.filter(recipient=user, is_starred=True, is_deleted=False).order_by("-created_at")

    return base.filter(recipient=user, folder="inbox", is_deleted=False).order_by("-created_at")


# ============================================================
# INBOX / FOLDER LIST
# ============================================================

@login_required
def inbox(request, folder="inbox"):
    qs = _folder_qs(request.user, folder)

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    unread_count = Message.objects.filter(
        recipient=request.user, folder="inbox", is_read=False, is_deleted=False
    ).count()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        html = render_to_string(
            "menntrix/_message_rows.html",
            {"messages": page_obj, "folder": folder, "user": request.user},
            request=request,
        )
        return JsonResponse({
            "html": html,
            "has_next": page_obj.has_next(),
            "next_page": page_obj.next_page_number() if page_obj.has_next() else None,
        })

    return render(request, "menntrix/message_inbox.html", {
        "messages": page_obj,
        "folder": folder,
        "unread_count": unread_count,
    })


# ============================================================
# VIEW A SINGLE MESSAGE
# ============================================================

@login_required
def message_view(request, message_id):
    msg = get_object_or_404(Message, id=message_id)

    if msg.sender_id != request.user.id and msg.recipient_id != request.user.id:
        flash.error(request, "You don't have access to that message.")
        return redirect("message_inbox")

    if msg.recipient_id == request.user.id and not msg.is_read:
        msg.is_read = True
        msg.save(update_fields=["is_read"])

    attachments = msg.attachments.all()

    return render(request, "menntrix/message_view.html", {
        "message": msg,
        "attachments": attachments,
    })


# ============================================================
# COMPOSE / REPLY / DRAFT EDIT
# ============================================================

@login_required
def message_compose(request):
    reply_to_id = request.GET.get("reply_to")
    draft_id = request.GET.get("draft")
    group_prefill_id = request.GET.get("group")

    prefill = {
        "subject": "",
        "body": "",
        "recipient_id": None,
        "recipient_ids": [],
        "group_id": None,
    }

    if reply_to_id:
        parent = Message.objects.filter(id=reply_to_id).first()
        if parent:
            prefill["subject"] = (
                parent.subject if parent.subject.startswith("Re:")
                else f"Re: {parent.subject or '(no subject)'}"
            )
            prefill["body"] = (
                f"\n\n---\nOn {parent.created_at:%b %d, %Y %H:%M}, "
                f"{parent.sender.username} wrote:\n{parent.body}"
            )
            if parent.recipient_id == request.user.id:
                prefill["recipient_id"] = parent.sender_id

    if draft_id:
        draft = Message.objects.filter(
            id=draft_id, sender=request.user, folder="drafts"
        ).first()
        if draft:
            prefill["subject"] = draft.subject
            prefill["body"] = draft.body
            prefill["recipient_id"] = draft.recipient_id
            prefill["group_id"] = draft.group_id

    if group_prefill_id:
        g = Group.objects.filter(id=group_prefill_id, owner=request.user).first()
        if not g:
            g = Group.objects.filter(
                id=group_prefill_id, members__user=request.user
            ).first()
        if g:
            prefill["group_id"] = g.id

    # ---- Handle POST ----
    if request.method == "POST":
        action = request.POST.get("action", "SEND").upper()

        recipient_id = request.POST.get("recipient_id")
        recipient_ids = request.POST.getlist("recipient_ids")
        group_id = request.POST.get("group_id")
        subject = (request.POST.get("subject") or "").strip() or "(no subject)"
        body = (request.POST.get("body") or "").strip()

        is_draft = (action == "SAVE DRAFT")

        files = request.FILES.getlist("attachments")
        links = [request.POST.get(f"link_{i}") for i in range(1, 6)]
        texts = [request.POST.get(f"text_{i}") for i in range(1, 6)]
        links = [u for u in links if u]
        texts = [t for t in texts if t]

        # ---- Group send ----
        if group_id:
            group = get_object_or_404(Group, id=group_id)

            if is_draft:
                draft = Message.objects.create(
                    sender=request.user,
                    group=group,
                    subject=subject,
                    body=body,
                    folder="drafts",
                )
                _save_attachments(draft, files, links, texts)
                _log(request.user, "draft_saved", "message", draft.id,
                     f"Draft to group '{group.name}'", request)
                flash.success(request, "Draft saved.")
                return redirect("message_drafts")

            sent_copy = Message.objects.create(
                sender=request.user,
                group=group,
                subject=subject,
                body=body,
                folder="sent",
            )
            _save_attachments(sent_copy, files, links, texts)

            for m in group.members.all():
                if m.user_id != request.user.id:
                    inbox_copy = Message.objects.create(
                        sender=request.user,
                        recipient=m.user,
                        group=group,
                        subject=subject,
                        body=body,
                        folder="inbox",
                        parent=sent_copy,
                    )
                    _copy_attachments(sent_copy, inbox_copy)

            _log(request.user, "message_sent", "group", group.id,
                 f"To group '{group.name}'", request)
            flash.success(request, f"Message sent to group '{group.name}'.")
            return redirect("message_inbox")

        # ---- Single recipient ----
        if recipient_id:
            recipient = get_object_or_404(UserAccount, id=recipient_id)

            if is_draft:
                draft = Message.objects.create(
                    sender=request.user,
                    recipient=recipient,
                    subject=subject,
                    body=body,
                    folder="drafts",
                )
                _save_attachments(draft, files, links, texts)
                _log(request.user, "draft_saved", "message", draft.id,
                     f"Draft to {recipient.username}", request)
                flash.success(request, "Draft saved.")
                return redirect("message_drafts")

            sent_copy = Message.objects.create(
                sender=request.user,
                recipient=recipient,
                subject=subject,
                body=body,
                folder="sent",
            )
            _save_attachments(sent_copy, files, links, texts)

            inbox_copy = Message.objects.create(
                sender=request.user,
                recipient=recipient,
                subject=subject,
                body=body,
                folder="inbox",
                parent=sent_copy,
            )
            _copy_attachments(sent_copy, inbox_copy)

            _log(request.user, "message_sent", "message", sent_copy.id,
                 f"To {recipient.username}", request)
            flash.success(request, f"Message sent to {recipient.username}.")
            return redirect("message_inbox")

        # ---- Multi recipient ----
        if recipient_ids:
            if is_draft:
                flash.error(request, "Drafts must have exactly one recipient.")
                return redirect("message_compose")

            for rid in recipient_ids:
                recipient = UserAccount.objects.filter(id=rid).first()
                if not recipient:
                    continue
                sent_copy = Message.objects.create(
                    sender=request.user,
                    recipient=recipient,
                    subject=subject,
                    body=body,
                    folder="sent",
                )
                _save_attachments(sent_copy, files, links, texts)

                inbox_copy = Message.objects.create(
                    sender=request.user,
                    recipient=recipient,
                    subject=subject,
                    body=body,
                    folder="inbox",
                    parent=sent_copy,
                )
                _copy_attachments(sent_copy, inbox_copy)

            _log(request.user, "message_sent", "message", "",
                 f"To {len(recipient_ids)} people", request)
            flash.success(request, f"Message sent to {len(recipient_ids)} people.")
            return redirect("message_inbox")

        flash.error(request, "Please choose at least one recipient.")
        return redirect("message_compose")

    # ---- GET: show the compose form ----
    all_users = UserAccount.objects.exclude(id=request.user.id).order_by("username")[:500]
    groups = Group.objects.filter(owner=request.user)

    return render(request, "menntrix/message_compose.html", {
        "all_users": all_users,
        "groups": groups,
        "prefill": prefill,
    })


# ============================================================
# DRAFT ACTIONS
# ============================================================

@login_required
def draft_send(request, message_id):
    """Convert a draft to a real sent message."""
    draft = get_object_or_404(
        Message, id=message_id, sender=request.user, folder="drafts"
    )

    if draft.group_id:
        group = draft.group
        sent_copy = Message.objects.create(
            sender=request.user,
            group=group,
            subject=draft.subject or "(no subject)",
            body=draft.body,
            folder="sent",
        )
        _copy_attachments(draft, sent_copy)

        for m in group.members.all():
            if m.user_id != request.user.id:
                inbox_copy = Message.objects.create(
                    sender=request.user,
                    recipient=m.user,
                    group=group,
                    subject=draft.subject or "(no subject)",
                    body=draft.body,
                    folder="inbox",
                    parent=sent_copy,
                )
                _copy_attachments(draft, inbox_copy)

        draft.delete()
        _log(request.user, "message_sent", "group", group.id,
             f"Draft sent to group '{group.name}'", request)
        flash.success(request, f"Draft sent to group '{group.name}'.")
        return redirect("message_inbox")

    if not draft.recipient_id:
        flash.error(request, "Draft has no recipient.")
        return redirect("message_drafts")

    sent_copy = Message.objects.create(
        sender=request.user,
        recipient=draft.recipient,
        subject=draft.subject or "(no subject)",
        body=draft.body,
        folder="sent",
    )
    _copy_attachments(draft, sent_copy)

    inbox_copy = Message.objects.create(
        sender=request.user,
        recipient=draft.recipient,
        subject=draft.subject or "(no subject)",
        body=draft.body,
        folder="inbox",
        parent=sent_copy,
    )
    _copy_attachments(draft, inbox_copy)

    draft.delete()
    _log(request.user, "message_sent", "message", sent_copy.id,
         f"Draft sent to {draft.recipient.username}", request)
    flash.success(request, f"Message sent to {draft.recipient.username}.")
    return redirect("message_inbox")


@login_required
def draft_delete(request, message_id):
    draft = get_object_or_404(Message, id=message_id, sender=request.user, folder="drafts")
    draft.delete()
    flash.success(request, "Draft deleted.")
    return redirect("message_drafts")


# ============================================================
# STAR / TRASH / RESTORE
# ============================================================

@login_required
def message_star(request, message_id):
    msg = get_object_or_404(Message, id=message_id)

    if msg.recipient_id != request.user.id:
        flash.error(request, "You can only star messages you received.")
        return redirect(request.META.get("HTTP_REFERER", "message_inbox"))

    msg.is_starred = not msg.is_starred
    msg.save(update_fields=["is_starred"])
    return redirect(request.META.get("HTTP_REFERER", "message_inbox"))


@login_required
def message_trash(request, message_id):
    msg = get_object_or_404(Message, id=message_id)

    if msg.sender_id != request.user.id and msg.recipient_id != request.user.id:
        flash.error(request, "You don't have access to that message.")
        return redirect("message_inbox")

    msg.is_deleted = True
    msg.save(update_fields=["is_deleted"])
    flash.success(request, "Message moved to trash.")
    return redirect("message_inbox")


@login_required
def message_restore(request, message_id):
    msg = get_object_or_404(Message, id=message_id)

    if msg.sender_id != request.user.id and msg.recipient_id != request.user.id:
        flash.error(request, "You don't have access to that message.")
        return redirect("message_trash_folder")

    msg.is_deleted = False
    msg.save(update_fields=["is_deleted"])
    flash.success(request, "Message restored.")
    return redirect("message_trash_folder")


@login_required
def message_delete_forever(request, message_id):
    msg = get_object_or_404(Message, id=message_id)

    if msg.sender_id != request.user.id and msg.recipient_id != request.user.id:
        flash.error(request, "You don't have access to that message.")
        return redirect("message_trash_folder")

    msg.delete()
    flash.success(request, "Message deleted permanently.")
    return redirect("message_trash_folder")


@login_required
def trash_empty(request):
    if request.method != "POST":
        return redirect("message_trash_folder")

    count, _ = Message.objects.filter(
        Q(recipient=request.user) | Q(sender=request.user),
        is_deleted=True,
    ).delete()

    _log(request.user, "trash_empty", "message", "", f"Emptied {count} messages", request)
    flash.success(request, f"Trash emptied ({count} messages deleted).")
    return redirect("message_trash_folder")


# ============================================================
# GROUP MANAGEMENT
# ============================================================

@login_required
def group_list(request):
    owned = Group.objects.filter(owner=request.user).order_by("-created_at")
    member_of = (
        Group.objects
        .filter(members__user=request.user)
        .exclude(owner=request.user)
        .distinct()
        .order_by("-created_at")
    )
    return render(request, "menntrix/group_list.html", {
        "owned": owned,
        "member_of": member_of,
    })


@login_required
def group_create(request):
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if not name:
            flash.error(request, "Group name is required.")
            return redirect("group_create")

        group = Group.objects.create(owner=request.user, name=name)
        GroupMember.objects.create(group=group, user=request.user)

        member_ids = request.POST.getlist("member_ids")
        for uid in member_ids:
            u = UserAccount.objects.filter(id=uid).exclude(id=request.user.id).first()
            if u:
                GroupMember.objects.get_or_create(group=group, user=u)

        _log(request.user, "group_created", "group", group.id,
             f"Created group '{name}'", request)
        flash.success(request, f"Group '{name}' created.")
        return redirect("group_detail", group_id=group.id)

    all_users = UserAccount.objects.exclude(id=request.user.id).order_by("username")[:500]
    return render(request, "menntrix/group_create.html", {"all_users": all_users})


@login_required
def group_detail(request, group_id):
    group = get_object_or_404(Group, id=group_id)

    is_owner = group.owner_id == request.user.id
    is_member = GroupMember.objects.filter(group=group, user=request.user).exists()
    if not (is_owner or is_member):
        flash.error(request, "You don't have access to that group.")
        return redirect("group_list")

    members = (
        GroupMember.objects
        .filter(group=group)
        .select_related("user")
        .order_by("added_at")
    )
    member_ids = [m.user_id for m in members]

    candidates = (
        UserAccount.objects
        .exclude(id__in=member_ids)
        .order_by("username")[:500]
    )

    return render(request, "menntrix/group_detail.html", {
        "group": group,
        "members": members,
        "candidates": candidates,
        "is_owner": is_owner,
    })


@login_required
def group_add_member(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    if group.owner_id != request.user.id:
        flash.error(request, "Only the owner can add members.")
        return redirect("group_detail", group_id=group.id)

    if request.method == "POST":
        user_ids = request.POST.getlist("user_ids")
        added = 0
        for uid in user_ids:
            u = UserAccount.objects.filter(id=uid).first()
            if u:
                _, created = GroupMember.objects.get_or_create(group=group, user=u)
                if created:
                    added += 1
        _log(request.user, "group_member_added", "group", group.id,
             f"Added {added} member(s) to '{group.name}'", request)
        flash.success(request, f"Added {added} member(s).")

    return redirect("group_detail", group_id=group.id)


@login_required
def group_remove_member(request, group_id, user_id):
    group = get_object_or_404(Group, id=group_id)
    if group.owner_id != request.user.id:
        flash.error(request, "Only the owner can remove members.")
        return redirect("group_detail", group_id=group.id)

    if user_id == group.owner_id:
        flash.error(request, "You cannot remove the owner.")
        return redirect("group_detail", group_id=group.id)

    GroupMember.objects.filter(group=group, user_id=user_id).delete()
    _log(request.user, "group_member_removed", "group", group.id,
         f"Removed a member from '{group.name}'", request)
    flash.success(request, "Member removed.")
    return redirect("group_detail", group_id=group.id)


@login_required
def group_rename(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    if group.owner_id != request.user.id:
        flash.error(request, "Only the owner can rename the group.")
        return redirect("group_detail", group_id=group.id)

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        if name:
            group.name = name
            group.save(update_fields=["name"])
            _log(request.user, "group_renamed", "group", group.id,
                 f"Renamed group to '{name}'", request)
            flash.success(request, "Group renamed.")
    return redirect("group_detail", group_id=group.id)


@login_required
def group_delete(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    if group.owner_id != request.user.id:
        flash.error(request, "Only the owner can delete the group.")
        return redirect("group_detail", group_id=group.id)

    if request.method == "POST":
        name = group.name
        group.delete()
        _log(request.user, "group_deleted", "group", group_id,
             f"Deleted group '{name}'", request)
        flash.success(request, f"Group '{name}' deleted.")
        return redirect("group_list")

    return redirect("group_detail", group_id=group.id)


@login_required
def group_leave(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    if group.owner_id == request.user.id:
        flash.error(request, "Owners must delete the group instead of leaving.")
        return redirect("group_detail", group_id=group.id)

    GroupMember.objects.filter(group=group, user=request.user).delete()
    _log(request.user, "group_left", "group", group.id,
         f"Left group '{group.name}'", request)
    flash.success(request, "You left the group.")
    return redirect("group_list")