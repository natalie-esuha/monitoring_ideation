from django.conf import settings
from django.core.management.base import BaseCommand

from wellbeing.alerts import normalize_phone
from wellbeing.sms import send_sms


class Command(BaseCommand):
    help = "Send one test SMS with the current provider to check it works"

    def add_arguments(self, parser):
        parser.add_argument("phone")

    def handle(self, *args, **options):
        phone = normalize_phone(options["phone"])
        status = send_sms(phone, "SafetyNet test message. If you can read this, alerts are working.")
        self.stdout.write(f"Provider {settings.SMS_PROVIDER} to {phone}: {status}")