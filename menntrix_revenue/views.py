from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from .models import UserEarnings, UserMonthlyUsage


@login_required
def my_earnings(request):
    earnings = (
        UserEarnings.objects
        .filter(user=request.user)
        .select_related("pool")
        .order_by("-pool__year", "-pool__month")
    )

    usage = (
        UserMonthlyUsage.objects
        .filter(user=request.user)
        .order_by("-year", "-month")[:12]
    )

    total_paid = (
        UserEarnings.objects
        .filter(user=request.user, paid=True)
        .aggregate(total=Sum("amount"))["total"] or 0
    )

    total_pending = (
        UserEarnings.objects
        .filter(user=request.user, paid=False)
        .aggregate(total=Sum("amount"))["total"] or 0
    )

    return render(request, "menntrix/my_earnings.html", {
        "earnings": earnings,
        "usage": usage,
        "total_paid": total_paid,
        "total_pending": total_pending,
    })