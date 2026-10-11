from datetime import timedelta

from django.utils import timezone

from .models import AlertThreshold, Alert
from .sms import send_sms


def normalize_phone(raw):
    phone = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
    if phone.startswith("+"):
        return phone
    if phone.startswith("0") and len(phone) == 10:
        return "+254" + phone[1:]
    return "+" + phone


def run_alert_check(now=None, dry_run=False):
    """Alert support people of anyone inactive past their threshold.

    One alert per support person per inactivity period: once an alert has been recorded
    after the person's last activity, no more are sent until they return and go quiet again.
    Failed deliveries are retried on the next run. The alert record is always saved, so it
    shows in the app and the database even when the SMS fails.
    """
    now = now or timezone.now()
    results = []
    thresholds = AlertThreshold.objects.filter(last_login__isnull=False).select_related("person__user")

    for threshold in thresholds:
        if now - threshold.last_login < timedelta(days=threshold.inactivity_days):
            continue
        days = (now - threshold.last_login).days
        person_user = threshold.person.user

        for link in threshold.person.support_links.select_related("designated__user"):
            already_alerted = Alert.objects.filter(
                threshold=threshold,
                designated=link.designated,
                date_sent__gt=threshold.last_login,
            ).exclude(delivery_status="failed").exists()
            if already_alerted:
                continue

            supporter = link.designated.user
            if dry_run:
                results.append((person_user, supporter, "dry-run"))
                continue

            body = (
                f"SafetyNet: {person_user.first_name} has not checked in for {days} days. "
                f"Please reach out to them when you can."
            )
            status = send_sms(normalize_phone(supporter.phone_no), body)
            Alert.objects.create(threshold=threshold, designated=link.designated, delivery_status=status)
            results.append((person_user, supporter, status))

    return results