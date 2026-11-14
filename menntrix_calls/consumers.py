import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from django.db.models import Q
from .models import CallSession, CallLocation, CallMessage


class CallConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return

        self.call_id = self.scope["url_route"]["kwargs"]["call_id"]
        self.room_group = f"call_{self.call_id}"
        self.user = user

        if not await self._user_in_call(user.id, self.call_id):
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group, self.channel_name)
        await self.accept()

        await self._touch_heartbeat()

        await self.channel_layer.group_send(self.room_group, {
            "type": "peer.join",
            "user_id": user.id,
            "username": user.username,
        })

    async def disconnect(self, close_code):
        if not hasattr(self, "room_group"):
            return
        user = getattr(self, "user", None)
        if user is None:
            return

        # End the call in the database
        await self._end_call(reason="peer_disconnected")
        
        # Tell the call room
        await self.channel_layer.group_send(self.room_group, {
            "type": "call.ended",
            "sender_id": user.id,
        })
        await self.channel_layer.group_send(self.room_group, {
            "type": "peer.leave",
            "user_id": user.id,
            "username": user.username,
        })
        
        # Tell BOTH users' global listeners to redirect instantly
        call = await self._get_call()
        if call:
            await self.channel_layer.group_send(f"user_{call.caller_id}", {
                "type": "call_ended",
                "call_id": call.call_id,
            })
            await self.channel_layer.group_send(f"user_{call.callee_id}", {
                "type": "call_ended",
                "call_id": call.call_id,
            })

        await self.channel_layer.group_discard(self.room_group, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except Exception:
            return

        kind = data.get("type")

        if kind in ("offer", "answer", "ice"):
            await self.channel_layer.group_send(self.room_group, {
                "type": "signal",
                "sender_id": self.user.id,
                "signal_type": kind,
                "payload": data.get("payload", {}),
            })

        elif kind == "chat":
            text = (data.get("text") or "").strip()
            if text:
                await self._save_chat(text)
                await self.channel_layer.group_send(self.room_group, {
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
                await self.channel_layer.group_send(self.room_group, {
                    "type": "location",
                    "sender_id": self.user.id,
                    "username": self.user.username,
                    "lat": lat,
                    "lng": lng,
                })

        elif kind == "ping":
            await self._touch_heartbeat()

        elif kind == "end":
            await self._end_call(reason="user_hung_up")
            
            # Tell the call room to cleanup UI
            await self.channel_layer.group_send(self.room_group, {
                "type": "call.ended",
                "sender_id": self.user.id,
            })
            
            # Tell BOTH users' global listeners to redirect instantly
            call = await self._get_call()
            if call:
                await self.channel_layer.group_send(f"user_{call.caller_id}", {
                    "type": "call_ended",
                    "call_id": call.call_id,
                })
                await self.channel_layer.group_send(f"user_{call.callee_id}", {
                    "type": "call_ended",
                    "call_id": call.call_id,
                })

    # ---------- group handlers ----------
    async def peer_join(self, event):
        await self.send(text_data=json.dumps({
            "type": "peer_join",
            "user_id": event["user_id"],
            "username": event["username"],
        }))

    async def peer_leave(self, event):
        await self.send(text_data=json.dumps({
            "type": "peer_leave",
            "user_id": event["user_id"],
            "username": event["username"],
        }))

    async def signal(self, event):
        if event["sender_id"] == self.user.id:
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

    async def call_ended(self, event):
        await self.send(text_data=json.dumps({
            "type": "call_ended",
            "sender_id": event["sender_id"],
        }))

    # ---------- db helpers ----------
    @database_sync_to_async
    def _user_in_call(self, user_id, call_id):
        return CallSession.objects.filter(call_id=call_id).filter(
            Q(caller_id=user_id) | Q(callee_id=user_id)
        ).exists()

    @database_sync_to_async
    def _get_call(self):
        return CallSession.objects.filter(call_id=self.call_id).first()

    @database_sync_to_async
    def _save_chat(self, text):
        call = CallSession.objects.filter(call_id=self.call_id).first()
        if call:
            CallMessage.objects.create(call=call, sender=self.user, text=text)

    @database_sync_to_async
    def _save_location(self, lat, lng, acc):
        call = CallSession.objects.filter(call_id=self.call_id).first()
        if call:
            CallLocation.objects.create(
                call=call, user=self.user, latitude=lat, longitude=lng, accuracy_m=acc
            )

    @database_sync_to_async
    def _touch_heartbeat(self):
        CallSession.objects.filter(call_id=self.call_id).update(
            last_heartbeat=timezone.now()
        )

    @database_sync_to_async
    def _end_call(self, reason="user_hung_up"):
        call = CallSession.objects.filter(call_id=self.call_id).first()
        if call and call.status != "ended":
            call.status = "ended"
            call.ended_at = timezone.now()
            call.ended_reason = reason
            if call.answered_at:
                call.duration_sec = int((call.ended_at - call.answered_at).total_seconds())
            call.save()


class CallListenerConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close()
            return

        self.user = user
        self.group_name = f"user_{user.id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        pass

    async def incoming_call(self, event):
        await self.send(text_data=json.dumps({
            "type": "incoming_call",
            "call_id": event["call_id"],
            "caller_id": event["caller_id"],
            "caller_username": event["caller_username"],
            "caller_name": event["caller_name"],
            "caller_avatar": event.get("caller_avatar", ""),
            "call_type": event["call_type"],
            "url": event["url"],
        }))

    async def call_cancelled(self, event):
        await self.send(text_data=json.dumps({
            "type": "call_cancelled",
            "call_id": event["call_id"],
        }))

    async def call_accepted(self, event):
        await self.send(text_data=json.dumps({
            "type": "call_accepted",
            "call_id": event["call_id"],
            "url": event["url"],
        }))

    async def call_rejected(self, event):
        await self.send(text_data=json.dumps({
            "type": "call_rejected",
            "call_id": event["call_id"],
        }))

    async def call_ended(self, event):
        await self.send(text_data=json.dumps({
            "type": "call_ended",
            "call_id": event["call_id"],
        }))