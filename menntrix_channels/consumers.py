import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.db import models as dj_models
from django.utils import timezone
from .models import Channel, ChannelComment, ChannelViewer, ChannelSubscription


class ChannelConsumer(AsyncWebsocketConsumer):

    # ------------------------------------------------------------
    # CONNECT
    # ------------------------------------------------------------
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return

        self.slug = self.scope["url_route"]["kwargs"]["slug"]
        self.group_name = f"channel_{self.slug}"
        self.user = user

        ch = await self._get_channel()
        if not ch or not ch["is_active"]:
            await self.close()
            return

        self.is_host = ch["owner_id"] == user.id

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await self._mark_joined()
        new_count = await self._viewer_count()

        await self.channel_layer.group_send(self.group_name, {
            "type": "viewer.join",
            "user_id": user.id,
            "username": user.username,
            "viewer_count": new_count,
        })

        # Send recent comments to the joiner
        recent = await self._recent_comments(30)
        await self.send(text_data=json.dumps({
            "type": "comments_snapshot",
            "comments": recent,
        }))

    # ------------------------------------------------------------
    # DISCONNECT
    # ------------------------------------------------------------
    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self._mark_left()
            new_count = await self._viewer_count()
            await self.channel_layer.group_send(self.group_name, {
                "type": "viewer.leave",
                "user_id": getattr(self, "user", None) and self.user.id,
                "username": getattr(self, "user", None) and self.user.username,
                "viewer_count": new_count,
            })
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # ------------------------------------------------------------
    # RECEIVE
    # ------------------------------------------------------------
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except Exception:
            return

        kind = data.get("type")

        if kind == "comment":
            text = (data.get("text") or "").strip()[:2000]
            if text:
                cmt = await self._save_comment(text)
                if cmt and cmt.get("id"):
                    await self.channel_layer.group_send(self.group_name, {
                        "type": "comment",
                        "id": cmt["id"],
                        "user_id": self.user.id,
                        "username": self.user.username,
                        "text": text,
                        "created_at": cmt["created_at"],
                    })

        elif kind == "signal":
            # host ↔ viewer SDP/ICE relay
            target_id = data.get("target_id")
            await self.channel_layer.group_send(self.group_name, {
                "type": "signal",
                "sender_id": self.user.id,
                "target_id": target_id,
                "signal_type": data.get("signal_type"),
                "payload": data.get("payload", {}),
                "is_host": self.is_host,
            })

        elif kind == "stream_state":
            state = data.get("state")
            if self.is_host and state in ("live", "ended"):
                await self._set_live(state == "live")
                await self.channel_layer.group_send(self.group_name, {
                    "type": "stream.state",
                    "state": state,
                })

    # ------------------------------------------------------------
    # GROUP HANDLERS
    # ------------------------------------------------------------
    async def viewer_join(self, event):
        await self.send(text_data=json.dumps({
            "type": "viewer_join",
            "user_id": event["user_id"],
            "username": event["username"],
            "viewer_count": event["viewer_count"],
        }))

    async def viewer_leave(self, event):
        await self.send(text_data=json.dumps({
            "type": "viewer_leave",
            "user_id": event["user_id"],
            "username": event["username"],
            "viewer_count": event["viewer_count"],
        }))

    async def comment(self, event):
        await self.send(text_data=json.dumps({
            "type": "comment",
            "id": event["id"],
            "user_id": event["user_id"],
            "username": event["username"],
            "text": event["text"],
            "created_at": event["created_at"],
        }))

    async def signal(self, event):
        if event["sender_id"] == self.user.id:
            return
        # Filter by target if present (cast to int for safety)
        target = event.get("target_id")
        if target is not None:
            try:
                if int(target) != self.user.id:
                    return
            except (TypeError, ValueError):
                return
        await self.send(text_data=json.dumps({
            "type": "signal",
            "sender_id": event["sender_id"],
            "signal_type": event["signal_type"],
            "payload": event["payload"],
            "is_host": event["is_host"],
        }))

    async def stream_state(self, event):
        await self.send(text_data=json.dumps({
            "type": "stream_state",
            "state": event["state"],
        }))

    # ------------------------------------------------------------
    # DB HELPERS
    # ------------------------------------------------------------
    @database_sync_to_async
    def _get_channel(self):
        c = Channel.objects.filter(slug=self.slug).first()
        if not c:
            return None
        return {"owner_id": c.owner_id, "is_active": c.is_active}

    @database_sync_to_async
    def _mark_joined(self):
        c = Channel.objects.filter(slug=self.slug).first()
        if not c:
            return
        ChannelViewer.objects.update_or_create(
            channel=c, user=self.user, defaults={"left_at": None}
        )

    @database_sync_to_async
    def _mark_left(self):
        ChannelViewer.objects.filter(
            channel__slug=self.slug, user=self.user, left_at__isnull=True
        ).update(left_at=timezone.now())

    @database_sync_to_async
    def _viewer_count(self):
        return ChannelViewer.objects.filter(
            channel__slug=self.slug, left_at__isnull=True
        ).count()

    @database_sync_to_async
    def _recent_comments(self, limit=30):
        qs = (
            ChannelComment.objects
            .filter(channel__slug=self.slug)
            .select_related("user")
            .order_by("-created_at")[:limit]
        )
        return [
            {
                "id": c.id,
                "user_id": c.user_id,
                "username": c.user.username,
                "text": c.text,
                "created_at": c.created_at.isoformat(),
            }
            for c in reversed(list(qs))
        ]

    @database_sync_to_async
    def _save_comment(self, text):
        c = Channel.objects.filter(slug=self.slug).first()
        if not c:
            return {"id": None, "created_at": None}
        cmt = ChannelComment.objects.create(channel=c, user=self.user, text=text)
        # Atomic increment of the denormalized counter
        Channel.objects.filter(id=c.id).update(
            comment_count=dj_models.F("comment_count") + 1
        )
        return {"id": cmt.id, "created_at": cmt.created_at.isoformat()}

    @database_sync_to_async
    def _set_live(self, is_live):
        now = timezone.now()
        if is_live:
            Channel.objects.filter(slug=self.slug).update(
                is_live=True,
                last_stream_at=now,
                ended_at=None,
            )
        else:
            Channel.objects.filter(slug=self.slug).update(
                is_live=False,
                ended_at=now,
                viewer_count=0,
            )

    # ------------------------------------------------------------
    # (OPTIONAL) NOTIFY SUBSCRIBERS WHEN HOST GOES LIVE
    # Call this from your go-live view, not from the consumer,
    # to avoid slowing down the WS handshake.
    # ------------------------------------------------------------
    @database_sync_to_async
    def _get_subscribers(self):
        return list(
            ChannelSubscription.objects
            .filter(channel__slug=self.slug, is_active=True, notify_on_live=True)
            .values_list("user_id", flat=True)
        )