from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from wellbeing.models import AlertThreshold


class Command(BaseCommand):
    help = "Demo helper: pretend a person last used the app N days ago"

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("days", type=int)

    def handle(self, *args, **options):
        when = timezone.now() - timedelta(days=options["days"])
        updated = AlertThreshold.objects.filter(
            person__user__email__iexact=options["email"]
        ).update(last_login=when)
        if not updated:
            raise CommandError("No person at risk found with that email.")
        self.stdout.write(f"Done. Last activity is now {options['days']} days ago.")