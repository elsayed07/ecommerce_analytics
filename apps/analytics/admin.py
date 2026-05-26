from django.contrib import admin

from .models import AnalyticsSnapshot


@admin.register(AnalyticsSnapshot)
class AnalyticsSnapshotAdmin(admin.ModelAdmin):
    list_display = ["snapshot_type", "period_start", "period_end", "created_at"]
    list_filter = ["snapshot_type"]
