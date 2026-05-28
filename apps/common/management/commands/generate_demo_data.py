from django.core.management.base import BaseCommand, CommandError

from services import demo_data_service


class Command(BaseCommand):
    help = "Generate realistic synthetic demo data for development and demos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--orders",
            type=int,
            default=demo_data_service.DEFAULT_ORDERS,
            help="Number of orders to generate.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=None,
            help="Seed for reproducible output. Omit for random data.",
        )

    def handle(self, *args, **options):
        orders = options["orders"]
        if orders < 1:
            raise CommandError("--orders must be a positive integer.")

        counts = demo_data_service.generate_demo_data(orders=orders, seed=options["seed"])
        self.stdout.write(self.style.SUCCESS(f"Demo data created: {counts}"))
