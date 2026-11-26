from datetime import timedelta

from django.utils import timezone

from .models import AlertThreshold, Alert, Event
from .sms import send_sms

# Trigger events alert the support circle when the event is today or within this many days.
EVENT_ALERT_DAYS_BEFORE = 1


def normalize_phone(raw):
    phone = "".join(ch for ch in raw if ch.isdigit() or ch == "+")
    if phone.startswith("+"):
        return phone
    if phone.startswith("0") and len(phone) == 10:
        return "+254" + phone[1:]
    return "+" + phone


def _check_inactivity(now, dry_run):
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
                event__isnull=True,
                kind=Alert.INACTIVITY,
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
            Alert.objects.create(threshold=threshold, designated=link.designated,
                                 kind=Alert.INACTIVITY, delivery_status=status)
            results.append((person_user, supporter, status))
    return results


def _check_trigger_events(now, dry_run):
    results = []
    today = timezone.localtime(now).date()
    events = Event.objects.filter(
        type=Event.TRIGGER,
        date__gte=today,
        date__lte=today + timedelta(days=EVENT_ALERT_DAYS_BEFORE),
    ).select_related("user")

    for event in events:
        person = getattr(event.user, "person_profile", None)
        threshold = getattr(person, "threshold", None) if person else None
        if not threshold:
            continue

        for link in person.support_links.select_related("designated__user"):
            already_alerted = Alert.objects.filter(
                event=event, designated=link.designated
            ).exclude(delivery_status="failed").exists()
            if already_alerted:
                continue

            supporter = link.designated.user
            if dry_run:
                results.append((event.user, supporter, "dry-run (event)"))
                continue

            body = (
                f"SafetyNet: {event.user.first_name} has a hard day coming up on "
                f"{event.date:%d %b}. Please reach out to them when you can."
            )
            status = send_sms(normalize_phone(supporter.phone_no), body)
            Alert.objects.create(threshold=threshold, designated=link.designated,
                                 event=event, kind=Alert.TRIGGER, delivery_status=status)
            results.append((event.user, supporter, f"{status} (event)"))
    return results


def run_alert_check(now=None, dry_run=False):
    """Inactivity alerts and trigger event alerts. One alert per support person per
    inactivity period, and one per support person per trigger event. Failed deliveries
    are retried on the next run. The alert record is always saved."""
    now = now or timezone.now()
    return _check_inactivity(now, dry_run) + _check_trigger_events(now, dry_run)