import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Meeting, MeetingParticipant, MeetingMessage, MeetingLocation


class MeetingConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return

        self.uuid = self.scope["url_route"]["kwargs"]["uuid"]
        self.group_name = f"meeting_{self.uuid}"
        self.user = user

        # Verify meeting exists and is joinable
        meeting = await self._get_meeting()
        if not meeting:
            await self.close()
            return
        if not meeting["is_active"]:
            await self.close()
            return
        if meeting["is_locked"] and not await self._is_participant():
            await self.close()
            return

        # Enforce max participants
        current = await self._participant_count()
        if current >= meeting["max_participants"] and not await self._is_participant():
            await self.close()
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        await self._mark_joined()

        await self.channel_layer.group_send(self.group_name, {
            "type": "peer.join",
            "user_id": user.id,
            "username": user.username,
        })

        # Send existing participant list to the new joiner
        participants = await self._participant_ids()
        await self.send(text_data=json.dumps({
            "type": "participants_list",
            "participants": participants,
        }))

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self._mark_left()
            await self.channel_layer.group_send(self.group_name, {
                "type": "peer.leave",
                "user_id": getattr(self, "user", None) and self.user.id,
                "username": getattr(self, "user", None) and self.user.username,
            })
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except Exception:
            return

        kind = data.get("type")

        if kind in ("offer", "answer", "ice"):
            target_id = data.get("target_id")
            await self.channel_layer.group_send(self.group_name, {
                "type": "signal",
                "sender_id": self.user.id,
                "target_id": target_id,
                "signal_type": kind,
                "payload": data.get("payload", {}),
            })

        elif kind == "chat":
            text = (data.get("text") or "").strip()
            if text:
                await self._save_chat(text)
                await self.channel_layer.group_send(self.group_name, {
                    "type": "chat",
                    "sender_id": self.user.id,
                    "username": self.user.username,
                    "text": text,
                })

        elif kind == "location":
            lat = data.get("lat")
            lng = data.get("lng")
            acc = data.get("accuracy")
            if lat is not None and lng is not None:
                await self._save_location(lat, lng, acc)
                await self.channel_layer.group_send(self.group_name, {
                    "type": "location",
                    "sender_id": self.user.id,
                    "username": self.user.username,
                    "lat": lat,
                    "lng": lng,
                })

    async def peer_join(self, event):
        if event["user_id"] == self.user.id:
            return
        await self.send(text_data=json.dumps({
            "type": "peer_join",
            "user_id": event["user_id"],
            "username": event["username"],
        }))

    async def peer_leave(self, event):
        if event["user_id"] == self.user.id:
            return
        await self.send(text_data=json.dumps({
            "type": "peer_leave",
            "user_id": event["user_id"],
            "username": event["username"],
        }))

    async def signal(self, event):
        if event["sender_id"] == self.user.id:
            return
        if event.get("target_id") and event["target_id"] != self.user.id:
            return
        await self.send(text_data=json.dumps({
            "type": "signal",
            "signal_type": event["signal_type"],
            "payload": event["payload"],
            "sender_id": event["sender_id"],
        }))

    async def chat(self, event):
        await self.send(text_data=json.dumps({
            "type": "chat",
            "sender_id": event["sender_id"],
            "username": event["username"],
            "text": event["text"],
        }))

    async def location(self, event):
        if event["sender_id"] == self.user.id:
            return
        await self.send(text_data=json.dumps({
            "type": "location",
            "sender_id": event["sender_id"],
            "username": event["username"],
            "lat": event["lat"],
            "lng": event["lng"],
        }))

    async def meeting_ended(self, event):
        await self.send(text_data=json.dumps({"type": "meeting_ended"}))

    # --- DB helpers ---
    @database_sync_to_async
    def _get_meeting(self):
        m = Meeting.objects.filter(uuid=self.uuid).first()
        if not m:
            return None
        return {
            "is_active": m.is_active,
            "is_locked": m.is_locked,
            "max_participants": m.max_participants,
        }

    @database_sync_to_async
    def _is_participant(self):
        return MeetingParticipant.objects.filter(
            meeting_id=self.uuid, user=self.user, left_at__isnull=True
        ).exists()

    @database_sync_to_async
    def _participant_count(self):
        return MeetingParticipant.objects.filter(
            meeting_id=self.uuid, left_at__isnull=True
        ).count()

    @database_sync_to_async
    def _participant_ids(self):
        return list(
            MeetingParticipant.objects.filter(
                meeting_id=self.uuid, left_at__isnull=True
            ).values_list("user_id", flat=True)
        )

    @database_sync_to_async
    def _mark_joined(self):
        meeting = Meeting.objects.filter(uuid=self.uuid).first()
        if not meeting:
            return
        MeetingParticipant.objects.update_or_create(
            meeting=meeting,
            user=self.user,
            defaults={"left_at": None, "is_host": meeting.host_id == self.user.id},
        )

    @database_sync_to_async
    def _mark_left(self):
        MeetingParticipant.objects.filter(
            meeting_id=self.uuid, user=self.user, left_at__isnull=True
        ).update(left_at=timezone.now())

    @database_sync_to_async
    def _save_chat(self, text):
        m = Meeting.objects.filter(uuid=self.uuid).first()
        if m:
            MeetingMessage.objects.create(meeting=m, sender=self.user, text=text)

    @database_sync_to_async
    def _save_location(self, lat, lng, acc):
        m = Meeting.objects.filter(uuid=self.uuid).first()
        if m:
            MeetingLocation.objects.create(
                meeting=m, user=self.user, latitude=lat, longitude=lng, accuracy_m=acc,
            )