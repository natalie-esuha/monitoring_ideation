from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role, User, PersonAtRisk, DesignatedPerson, SupportLink
from wellbeing.alerts import run_alert_check, normalize_phone
from wellbeing.models import AlertThreshold, Alert, Event, SafetyPlan


def make_user(email, role_name, phone="+254712345678", first="Test", last="User"):
    role, _ = Role.objects.get_or_create(role_name=role_name)
    return User.objects.create_user(
        email=email,
        password="testpass123",
        first_name=first,
        last_name=last,
        phone_no=phone,
        gender="Female",
        role=role,
    )


class SafetyPlanTests(TestCase):
    def setUp(self):
        self.user = make_user("risk@example.com", Role.PERSON_AT_RISK)
        self.person = PersonAtRisk.objects.create(user=self.user)
        AlertThreshold.objects.create(person=self.person, inactivity_days=3)
        self.client.login(username="risk@example.com", password="testpass123")

    def test_safety_plan_saves(self):
        response = self.client.post(reverse("safety_plan"), {
            "action": "add",
            "section": "warning_signs",
            "text": "I stop replying to messages",
        })
        self.assertEqual(response.status_code, 302)
        plan = SafetyPlan.objects.get(person=self.person)
        self.assertIn("I stop replying to messages", plan.warning_signs)

    def test_safety_plan_rejects_invalid_section(self):
        response = self.client.post(reverse("safety_plan"), {
            "action": "add", "section": "not_a_section", "text": "x"})
        self.assertEqual(response.status_code, 200)  # form re-rendered with errors

    def test_safety_plan_rejects_text_over_200_characters(self):
        response = self.client.post(reverse("safety_plan"), {
            "action": "add", "section": "triggers", "text": "a" * 201})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            SafetyPlan.objects.filter(person=self.person, triggers__contains="a" * 201).exists()
        )


class AlertTests(TestCase):
    def setUp(self):
        self.risk_user = make_user("risk@example.com", Role.PERSON_AT_RISK,
                                   phone="+254711111111", first="Risk")
        self.person = PersonAtRisk.objects.create(user=self.risk_user)
        self.threshold = AlertThreshold.objects.create(person=self.person, inactivity_days=3)

        self.support_user = make_user("support@example.com", Role.DESIGNATED_PERSON,
                                      phone="0722222222", first="Support")
        self.designated = DesignatedPerson.objects.create(user=self.support_user)
        SupportLink.objects.create(person=self.person, designated=self.designated,
                                   relationship_type="Friend")

    def _set_last_login(self, days_ago):
        self.threshold.last_login = timezone.now() - timedelta(days=days_ago)
        self.threshold.save()

    @patch("wellbeing.alerts.send_sms", return_value="sent")
    def test_inactivity_alert_sent_when_threshold_exceeded(self, mock_sms):
        self._set_last_login(5)
        run_alert_check()
        self.assertEqual(Alert.objects.count(), 1)
        alert = Alert.objects.get()
        self.assertEqual(alert.delivery_status, "sent")
        self.assertEqual(alert.designated, self.designated)
        self.assertIsNone(alert.event)
        mock_sms.assert_called_once()
        self.assertEqual(mock_sms.call_args[0][0], "+254722222222")

    @patch("wellbeing.alerts.send_sms", return_value="sent")
    def test_no_alert_when_within_threshold(self, mock_sms):
        self._set_last_login(1)
        run_alert_check()
        self.assertEqual(Alert.objects.count(), 0)
        mock_sms.assert_not_called()

    @patch("wellbeing.alerts.send_sms", return_value="sent")
    def test_no_duplicate_inactivity_alert(self, mock_sms):
        self._set_last_login(5)
        run_alert_check()
        run_alert_check()
        self.assertEqual(Alert.objects.count(), 1)
        self.assertEqual(mock_sms.call_count, 1)

    @patch("wellbeing.alerts.send_sms", return_value="failed")
    def test_failed_alert_is_saved_and_retried(self, mock_sms):
        self._set_last_login(5)
        run_alert_check()
        run_alert_check()
        self.assertEqual(Alert.objects.filter(delivery_status="failed").count(), 2)
        self.assertEqual(mock_sms.call_count, 2)

    @patch("wellbeing.alerts.send_sms", return_value="sent")
    def test_trigger_event_today_sends_alert(self, mock_sms):
        event = Event.objects.create(
            name="Anniversary", type=Event.TRIGGER,
            date=timezone.localdate(), user=self.risk_user,
        )
        run_alert_check()
        alert = Alert.objects.get()
        self.assertEqual(alert.event, event)
        self.assertEqual(alert.delivery_status, "sent")
        mock_sms.assert_called_once()

    @patch("wellbeing.alerts.send_sms", return_value="sent")
    def test_normal_event_sends_no_alert(self, mock_sms):
        Event.objects.create(
            name="Birthday", type=Event.NORMAL,
            date=timezone.localdate(), user=self.risk_user,
        )
        run_alert_check()
        self.assertEqual(Alert.objects.count(), 0)
        mock_sms.assert_not_called()

    @patch("wellbeing.alerts.send_sms", return_value="sent")
    def test_distant_trigger_event_sends_no_alert(self, mock_sms):
        Event.objects.create(
            name="Exam", type=Event.TRIGGER,
            date=timezone.localdate() + timedelta(days=10), user=self.risk_user,
        )
        run_alert_check()
        self.assertEqual(Alert.objects.count(), 0)

    def test_normalize_phone(self):
        self.assertEqual(normalize_phone("0712345678"), "+254712345678")
        self.assertEqual(normalize_phone("+254712345678"), "+254712345678")
        self.assertEqual(normalize_phone("254712345678"), "+254712345678")


class ThresholdTests(TestCase):
    def setUp(self):
        self.user = make_user("risk@example.com", Role.PERSON_AT_RISK)
        self.person = PersonAtRisk.objects.create(user=self.user)
        self.threshold = AlertThreshold.objects.create(person=self.person, inactivity_days=3)
        self.client.login(username="risk@example.com", password="testpass123")

    def test_threshold_updates(self):
        response = self.client.post(reverse("threshold"), {"inactivity_days": 7})
        self.assertEqual(response.status_code, 302)
        self.threshold.refresh_from_db()
        self.assertEqual(self.threshold.inactivity_days, 7)

    def test_threshold_rejects_out_of_range(self):
        response = self.client.post(reverse("threshold"), {"inactivity_days": 31})
        self.assertEqual(response.status_code, 200)
        self.threshold.refresh_from_db()
        self.assertEqual(self.threshold.inactivity_days, 3)


class AccessControlTests(TestCase):
    def test_designated_person_cannot_open_safety_plan(self):
        make_user("support@example.com", Role.DESIGNATED_PERSON)
        self.client.login(username="support@example.com", password="testpass123")
        response = self.client.get(reverse("safety_plan"))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(reverse("safety_plan"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)