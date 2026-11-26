from django.db import models
from accounts.models import PersonAtRisk, DesignatedPerson, User


class Event(models.Model):
    NORMAL = "Normal"
    TRIGGER = "Trigger"

    id_event = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=30)
    description = models.TextField(blank=True)
    date = models.DateField()
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="events")


class SafetyPlan(models.Model):
    plan_id = models.AutoField(primary_key=True)
    person = models.OneToOneField(PersonAtRisk, on_delete=models.CASCADE, related_name="safety_plan")
    coping_strategy = models.TextField(blank=True)
    triggers = models.TextField(blank=True)
    warning_signs = models.TextField(blank=True)
    date_created = models.DateField(auto_now_add=True)


class HopeBoxItem(models.Model):
    item_id = models.AutoField(primary_key=True)
    person = models.ForeignKey(PersonAtRisk, on_delete=models.CASCADE, related_name="hope_items")
    item_type = models.CharField(max_length=30)
    title = models.CharField(max_length=100)
    file_url = models.FileField(upload_to="hopebox/", max_length=255, blank=True)
    date_added = models.DateField(auto_now_add=True)

    @property
    def is_image(self):
        return bool(self.file_url) and self.file_url.name.lower().endswith(
            (".jpg", ".jpeg", ".png", ".gif", ".webp")
        )


class MoodCheckIn(models.Model):
    FACES = [
        (1, "Very low", "bi-emoji-frown-fill"),
        (2, "Low", "bi-emoji-expressionless-fill"),
        (3, "Okay", "bi-emoji-neutral-fill"),
        (4, "Good", "bi-emoji-smile-fill"),
        (5, "Great", "bi-emoji-laughing-fill"),
    ]
    MOODS = [(value, label) for value, label, _ in FACES]

    checkin_id = models.AutoField(primary_key=True)
    person = models.ForeignKey(PersonAtRisk, on_delete=models.CASCADE, related_name="checkins")
    date = models.DateField()
    mood = models.PositiveSmallIntegerField(choices=MOODS)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("person", "date")

    @property
    def icon(self):
        return {v: i for v, _, i in self.FACES}.get(self.mood, "bi-emoji-neutral-fill")

    @property
    def label(self):
        return dict(self.MOODS).get(self.mood, "")


class AlertThreshold(models.Model):
    threshold_id = models.AutoField(primary_key=True)
    person = models.OneToOneField(PersonAtRisk, on_delete=models.CASCADE, related_name="threshold")
    inactivity_days = models.PositiveIntegerField(default=3)
    last_login = models.DateTimeField(null=True, blank=True)


class Alert(models.Model):
    INACTIVITY = "Inactivity"
    TRIGGER = "Trigger event"
    HELP = "Help request"

    alert_id = models.AutoField(primary_key=True)
    threshold = models.ForeignKey(AlertThreshold, on_delete=models.CASCADE, related_name="alerts")
    designated = models.ForeignKey(DesignatedPerson, on_delete=models.CASCADE, related_name="alerts")
    event = models.ForeignKey(Event, null=True, blank=True, on_delete=models.CASCADE, related_name="alerts")
    kind = models.CharField(max_length=20, default=INACTIVITY)
    date_sent = models.DateTimeField(auto_now_add=True)
    delivery_status = models.CharField(max_length=20, default="pending")