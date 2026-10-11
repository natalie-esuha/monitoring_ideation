from django.conf import settings
from django.core.management.base import BaseCommand

from wellbeing.alerts import run_alert_check
from wellbeing.sms import is_configured


class Command(BaseCommand):
    help = "Alert support people when someone has been inactive past their threshold"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Show who would be alerted without sending anything")

    def handle(self, *args, **options):
        provider = settings.SMS_PROVIDER
        ready = "ready" if is_configured(provider) else "NOT CONFIGURED"
        self.stdout.write(f"SMS provider: {provider} ({ready})")
        results = run_alert_check(dry_run=options["dry_run"])
        if not results:
            self.stdout.write("No alerts needed.")
        for person, supporter, status in results:
            self.stdout.write(f"{person} -> {supporter}: {status}")