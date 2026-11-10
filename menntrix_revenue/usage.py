from django.db import models as dj_models
from django.db import IntegrityError, transaction
from django.utils import timezone
from .models import UserMonthlyUsage


def _get_or_create(user, year=None, month=None):
    now = timezone.now()
    year = year or now.year
    month = month or now.month

    try:
        obj, _ = UserMonthlyUsage.objects.get_or_create(
            user=user, year=year, month=month,
        )
        return obj
    except IntegrityError:
        # Another concurrent request created it between our SELECT and INSERT.
        return UserMonthlyUsage.objects.get(user=user, year=year, month=month)


def _add(obj, field, minutes):
    """Atomically add `minutes` to `field` on the usage row."""
    if not minutes or minutes <= 0:
        return
    with transaction.atomic():
        UserMonthlyUsage.objects.filter(id=obj.id).update(
            **{field: dj_models.F(field) + int(minutes)}
        )


def add_call_minutes(user, minutes):
    """Add `minutes` to the user's monthly CALL counter."""
    if not minutes or minutes <= 0:
        return
    obj = _get_or_create(user)
    _add(obj, "call_minutes", minutes)


def add_meeting_minutes(user, minutes):
    """Add `minutes` to the user's monthly MEETING counter."""
    if not minutes or minutes <= 0:
        return
    obj = _get_or_create(user)
    _add(obj, "meeting_minutes", minutes)


def add_stream_minutes(user, minutes):
    """Add `minutes` to the user's monthly STREAM counter."""
    if not minutes or minutes <= 0:
        return
    obj = _get_or_create(user)
    _add(obj, "stream_minutes", minutes)