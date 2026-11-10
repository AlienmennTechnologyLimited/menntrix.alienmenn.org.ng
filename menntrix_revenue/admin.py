from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, F
from .models import EarningsPool, UserMonthlyUsage, UserEarnings
from .distribution import distribute_pool, undistribute_pool


# ============================================================
# EARNINGS POOL
# ============================================================
@admin.register(EarningsPool)
class EarningsPoolAdmin(admin.ModelAdmin):
    list_display = (
        "label", "total_amount", "status_badge",
        "total_minutes_display", "payout_count", "distributed_at",
    )
    list_filter = ("status", "year")
    ordering = ("-year", "-month")
    actions = ["action_distribute", "action_undistribute"]

    def status_badge(self, obj):
        if obj.status == "distributed":
            return format_html(
                '<span style="color:#4caf50;font-weight:bold;">DISTRIBUTED</span>'
            )
        return format_html(
            '<span style="color:#ff9800;font-weight:bold;">OPEN</span>'
        )
    status_badge.short_description = "Status"

    def total_minutes_display(self, obj):
        return obj.total_minutes
    total_minutes_display.short_description = "Total minutes"

    def payout_count(self, obj):
        return obj.payouts.count()
    payout_count.short_description = "Payouts"

    @admin.action(description="Distribute selected pool(s)")
    def action_distribute(self, request, queryset):
        ok_count = 0
        errs = []
        for pool in queryset:
            result = distribute_pool(pool.id)
            if result.get("ok"):
                ok_count += 1
            else:
                errs.append(f"{pool.label}: {result.get('error')}")

        if ok_count:
            self.message_user(request, f"Distributed {ok_count} pool(s).")
        if errs:
            self.message_user(request, "Errors: " + "; ".join(errs), level="error")

    @admin.action(description="Undo distribution (delete payouts, reopen pool)")
    def action_undistribute(self, request, queryset):
        count = 0
        for pool in queryset:
            result = undistribute_pool(pool.id)
            if result.get("ok"):
                count += 1
        self.message_user(request, f"Undid {count} pool(s).")


# ============================================================
# USER MONTHLY USAGE
# ============================================================
@admin.register(UserMonthlyUsage)
class UserMonthlyUsageAdmin(admin.ModelAdmin):
    list_display = (
        "user", "year", "month",
        "call_minutes", "meeting_minutes", "stream_minutes",
        "total_minutes_display",
    )
    list_filter = ("year", "month")
    search_fields = ("user__email", "user__username")
    ordering = ("-year", "-month", "user__username")

    def total_minutes_display(self, obj):
        return obj.total_minutes
    total_minutes_display.short_description = "Total"


# ============================================================
# USER EARNINGS
# ============================================================
@admin.register(UserEarnings)
class UserEarningsAdmin(admin.ModelAdmin):
    list_display = (
        "user", "pool_label", "minutes",
        "share_percent", "amount", "paid_badge",
    )
    list_filter = ("paid", "pool__year", "pool__month")
    search_fields = ("user__email", "user__username")
    ordering = ("-pool__year", "-pool__month", "-amount")
    actions = ["action_mark_paid", "action_mark_unpaid"]

    def pool_label(self, obj):
        return obj.pool.label
    pool_label.short_description = "Pool"

    def paid_badge(self, obj):
        if obj.paid:
            return format_html(
                '<span style="color:#4caf50;font-weight:bold;">PAID</span>'
            )
        return format_html(
            '<span style="color:#ff9800;font-weight:bold;">PENDING</span>'
        )
    paid_badge.short_description = "Status"

    @admin.action(description="Mark selected as PAID")
    def action_mark_paid(self, request, queryset):
        from django.utils import timezone
        count = queryset.update(paid=True, paid_at=timezone.now())
        self.message_user(request, f"Marked {count} payout(s) as paid.")

    @admin.action(description="Mark selected as UNPAID")
    def action_mark_unpaid(self, request, queryset):
        count = queryset.update(paid=False, paid_at=None)
        self.message_user(request, f"Marked {count} payout(s) as unpaid.")