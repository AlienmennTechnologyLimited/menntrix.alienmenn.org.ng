from django.core.validators import MinValueValidator
from django.db import models
from django.conf import settings


# ============================================================
# EARNINGS POOL — one row per month
# ============================================================
class EarningsPool(models.Model):
    """
    A pool of money that gets distributed to active users.
    One row per month. Admin sets total_amount, then triggers
    distribution which creates UserEarnings rows.
    """

    STATUS_CHOICES = [
        ("open", "Open"),
        ("distributed", "Distributed"),
    ]

    year = models.IntegerField(validators=[MinValueValidator(2000)])
    month = models.IntegerField(validators=[MinValueValidator(1)])  # 1-12
    total_amount = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")

    created_at = models.DateTimeField(auto_now_add=True)
    distributed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "menntrix_earnings_pool"
        unique_together = ("year", "month")
        ordering = ["-year", "-month"]
        indexes = [
            models.Index(fields=["year", "month"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"Pool {self.year}-{self.month:02d} ({self.status})"

    @property
    def label(self):
        return f"{self.year}-{self.month:02d}"

    @property
    def total_minutes(self):
        """Sum of calls + meetings + streams for this month's users."""
        return (
            UserMonthlyUsage.objects
            .filter(year=self.year, month=self.month)
            .aggregate(
                total=models.Sum(
                    models.F("call_minutes")
                    + models.F("meeting_minutes")
                    + models.F("stream_minutes")
                )
            )
            .get("total") or 0
        )


# ============================================================
# USER MONTHLY USAGE — one row per user per month
# ============================================================
class UserMonthlyUsage(models.Model):
    """
    Tracks how many minutes a user spent on calls / meetings / streams
    during a given month.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menntrix_usage",
    )

    year = models.IntegerField()
    month = models.IntegerField()  # 1-12

    call_minutes = models.IntegerField(default=0)
    meeting_minutes = models.IntegerField(default=0)
    stream_minutes = models.IntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "menntrix_user_usage"
        unique_together = ("user", "year", "month")
        ordering = ["-year", "-month"]
        indexes = [
            models.Index(fields=["year", "month"]),
            models.Index(fields=["user", "year", "month"]),
        ]

    def __str__(self):
        return f"{self.user_id} {self.year}-{self.month:02d} = {self.total_minutes} min"

    @property
    def total_minutes(self):
        return (
            (self.call_minutes or 0)
            + (self.meeting_minutes or 0)
            + (self.stream_minutes or 0)
        )


# ============================================================
# USER EARNINGS — the output of a distribution
# ============================================================
class UserEarnings(models.Model):
    """
    How much a user earned from a specific pool.
    Created by the distribution algorithm.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="menntrix_earnings",
    )
    pool = models.ForeignKey(
        EarningsPool,
        on_delete=models.CASCADE,
        related_name="payouts",
    )

    minutes = models.IntegerField(default=0)
    share_percent = models.DecimalField(max_digits=7, decimal_places=3, default=0)
    amount = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "menntrix_user_earnings"
        unique_together = ("user", "pool")
        ordering = ["-pool__year", "-pool__month", "-amount"]
        indexes = [
            models.Index(fields=["user", "pool"]),
            models.Index(fields=["paid"]),
        ]

    def __str__(self):
        return f"{self.user_id} → {self.pool.label} = {self.amount}"