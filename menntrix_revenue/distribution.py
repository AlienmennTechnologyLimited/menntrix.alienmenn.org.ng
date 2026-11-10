from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
from .models import EarningsPool, UserMonthlyUsage, UserEarnings


TWO_PLACES = Decimal("0.01")


def _q(amount):
    """Round a Decimal to 2 decimal places, half-up."""
    return Decimal(amount).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def distribute_pool(pool_id):
    """
    Distribute a pool's money proportionally to each user's minutes.

    share_percent = (user_minutes / total_minutes) × 100
    amount        = (pool.total_amount × user_minutes) / total_minutes

    The last earner absorbs the rounding residual so the sum of all
    payouts exactly equals pool.total_amount.

    Returns a dict with a summary.
    """
    with transaction.atomic():
        try:
            pool = EarningsPool.objects.select_for_update().get(id=pool_id)
        except EarningsPool.DoesNotExist:
            return {"ok": False, "error": "Pool not found"}

        if pool.status == "distributed":
            return {"ok": False, "error": "Pool already distributed"}

        total_amt = Decimal(str(pool.total_amount or "0"))
        if total_amt <= 0:
            return {"ok": False, "error": "Pool has no money"}

        usages = list(
            UserMonthlyUsage.objects.filter(year=pool.year, month=pool.month)
        )
        if not usages:
            return {"ok": False, "error": "No usage for this month"}

        total_minutes = sum((u.total_minutes or 0) for u in usages)
        if total_minutes <= 0:
            return {"ok": False, "error": "Everyone has 0 minutes"}

        # Sort by minutes descending so the LAST earner is the smallest
        # earner — this keeps the residual impact minimal.
        earners = [u for u in usages if (u.total_minutes or 0) > 0]
        earners.sort(key=lambda u: u.total_minutes, reverse=True)
        skipped = len(usages) - len(earners)

        running = Decimal("0.00")
        created = 0

        for i, u in enumerate(earners):
            share_pct = (Decimal(u.total_minutes) / Decimal(total_minutes)) * 100

            if i == len(earners) - 1:
                # Last user absorbs the residual so the total matches.
                amount = total_amt - running
            else:
                amount = _q(total_amt * u.total_minutes / total_minutes)
                running += amount

            UserEarnings.objects.update_or_create(
                user=u.user,
                pool=pool,
                defaults={
                    "minutes": u.total_minutes,
                    "share_percent": _q(share_pct),
                    "amount": amount,
                },
            )
            created += 1

        pool.status = "distributed"
        pool.distributed_at = timezone.now()
        pool.save(update_fields=["status", "distributed_at"])

    return {
        "ok": True,
        "pool": pool.label,
        "created": created,
        "skipped": skipped,
        "total_minutes": total_minutes,
        "total_amount": float(total_amt),
    }


def undistribute_pool(pool_id):
    """
    Delete all unpaid UserEarnings for a pool, revert status to 'open'.
    Refuses if any earnings have been marked paid.
    """
    with transaction.atomic():
        try:
            pool = EarningsPool.objects.select_for_update().get(id=pool_id)
        except EarningsPool.DoesNotExist:
            return {"ok": False, "error": "Pool not found"}

        paid_count = UserEarnings.objects.filter(pool=pool, paid=True).count()
        if paid_count:
            return {
                "ok": False,
                "error": f"{paid_count} payouts already marked paid. Cannot undo.",
            }

        UserEarnings.objects.filter(pool=pool).delete()
        pool.status = "open"
        pool.distributed_at = None
        pool.save(update_fields=["status", "distributed_at"])

    return {"ok": True, "pool": pool.label}