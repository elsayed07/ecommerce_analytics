from django.core.management.base import BaseCommand

from services import analytics_service


class Command(BaseCommand):
    help = "Recompute analytics snapshots (revenue, top products, customers)."

    def handle(self, *args, **options):
        counts = analytics_service.build_snapshots()
        self.stdout.write(self.style.SUCCESS(f"Snapshots rebuilt: {counts}"))
