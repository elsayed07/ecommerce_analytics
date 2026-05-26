from django.db import models

from apps.common.models import BaseModel


class AnalyticsSnapshot(BaseModel):
    class Type(models.TextChoices):
        REVENUE_DAILY = "revenue_daily", "Revenue (daily)"
        REVENUE_WEEKLY = "revenue_weekly", "Revenue (weekly)"
        REVENUE_MONTHLY = "revenue_monthly", "Revenue (monthly)"
        TOP_PRODUCTS = "top_products", "Top products"
        CUSTOMERS = "customers", "Customers"
        FORECAST = "forecast", "Forecast"

    snapshot_type = models.CharField(max_length=32, choices=Type.choices)
    period_start = models.DateField()
    period_end = models.DateField()
    metrics = models.JSONField(default=dict)

    class Meta:
        unique_together = ("snapshot_type", "period_start", "period_end")
        ordering = ["snapshot_type", "period_start"]
        indexes = [models.Index(fields=["snapshot_type", "period_start"])]

    def __str__(self):
        return f"{self.snapshot_type} {self.period_start}..{self.period_end}"
