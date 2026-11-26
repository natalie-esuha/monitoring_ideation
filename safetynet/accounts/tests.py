from django.test import TestCase

# Create your tests here.
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.factories import PASSWORD, link, make_invitation, make_person, make_supporter
from accounts.forms import InviteRegisterForm, RegisterForm
from accounts.models import (
    DesignatedPerson, PersonAtRisk, Role, SupportInvitation, SupportLink, User,
)
from wellbeing.models import AlertThreshold


def register_data(**overrides):
    data = {
        "first_name": "Amina", "last_name": "Otieno", "email": "Amina@Example.com",
        "phone_no": "+254712345678", "gender": "Female",
        "password1": PASSWORD, "password2": PASSWORD,
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------- registration form
class RegisterFormTests(TestCase):
    def test_valid_registration_creates_person_at_risk(self):
        form = RegisterForm(data=register_data())
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.role_name, Role.PERSON_AT_RISK)
        self.assertTrue(PersonAtRisk.objects.filter(user=user).exists())

    def test_registration_creates_default_threshold_of_3_days(self):
        form = RegisterForm(data=register_data())
        form.is_valid()
        user = form.save()
        self.assertEqual(AlertThreshold.objects.get(person_id=user.pk).inactivity_days, 3)

    def test_email_is_lowercased(self):
        form = RegisterForm(data=register_data())
        form.is_valid()
        self.assertEqual(form.save().email, "amina@example.com")

    def test_password_is_hashed_not_stored_in_plain_text(self):
        form = RegisterForm(data=register_data())
        form.is_valid()
        user = form.save()
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))

    def test_duplicate_email_rejected(self):
        make_person(email="amina@example.com")
        form = RegisterForm(data=register_data())
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_duplicate_email_check_ignores_case(self):
        make_person(email="amina@example.com")
        form = RegisterForm(data=register_data(email="AMINA@EXAMPLE.COM"))
        self.assertFalse(form.is_valid())

    def test_mismatched_passwords_rejected(self):
        form = RegisterForm(data=register_data(password2="Different123"))
        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

    def test_short_password_rejected(self):
        form = RegisterForm(data=register_data(password1="short", password2="short"))
        self.assertFalse(form.is_valid())
        self.assertIn("password1", form.errors)

    def test_invalid_phone_rejected(self):
        for bad in ["abc", "12345", "+254-71-234"]:
            with self.subTest(phone=bad):
                self.assertFalse(RegisterForm(data=register_data(phone_no=bad)).is_valid())

    def test_missing_required_fields_rejected(self):
        self.assertFalse(RegisterForm(data={}).is_valid())


class InviteRegisterFormTests(TestCase):
    def setUp(self):
        _, self.person, _ = make_person()
        self.invitation = make_invitation(self.person, email="friend@example.com")

    def test_creates_designated_person_not_person_at_risk(self):
        data = register_data()
        data.pop("email")                      # email is locked to the invitation
        form = InviteRegisterForm(data=data, invitation=self.invitation)
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.role_name, Role.DESIGNATED_PERSON)
        self.assertTrue(DesignatedPerson.objects.filter(user=user).exists())
        self.assertFalse(PersonAtRisk.objects.filter(user=user).exists())
        self.assertEqual(user.email, "friend@example.com")

    def test_email_field_is_locked(self):
        form = InviteRegisterForm(invitation=self.invitation)
        self.assertTrue(form.fields["email"].disabled)


# ---------------------------------------------------------------- invitation model
class SupportInvitationModelTests(TestCase):
    def setUp(self):
        _, self.person, _ = make_person()

    def test_token_and_expiry_generated(self):
        inv = make_invitation(self.person)
        self.assertTrue(inv.token)
        self.assertGreater(len(inv.token), 20)
        remaining = inv.expires_at - timezone.now()
        self.assertTrue(timedelta(days=6, hours=23) < remaining <= timedelta(days=7))

    def test_tokens_are_unique(self):
        a = make_invitation(self.person, email="a@example.com")
        b = make_invitation(self.person, email="b@example.com")
        self.assertNotEqual(a.token, b.token)

    def test_email_is_stripped_and_lowercased(self):
        inv = SupportInvitation.objects.create(
            person=self.person, invitee_name="Sam", invitee_email="  Sam@Example.COM ",
            relationship_type="Friend")
        self.assertEqual(inv.invitee_email, "sam@example.com")

    def test_new_invitation_is_usable(self):
        self.assertTrue(make_invitation(self.person).is_usable)

    def test_expired_invitation_not_usable(self):
        inv = make_invitation(self.person)
        inv.expires_at = timezone.now() - timedelta(minutes=1)
        inv.save()
        self.assertFalse(inv.is_usable)

    def test_cancelled_and_accepted_not_usable(self):
        for status in (SupportInvitation.CANCELLED, SupportInvitation.ACCEPTED):
            with self.subTest(status=status):
                inv = make_invitation(self.person, email=f"{status}@example.com")
                inv.status = status
                inv.save()
                self.assertFalse(inv.is_usable)


# ---------------------------------------------------------------- register and login views
class RegisterAndLoginViewTests(TestCase):
    def test_register_creates_account_and_logs_in(self):
        response = self.client.post(reverse("register"), register_data())
        self.assertRedirects(response, reverse("dashboard"), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(email="amina@example.com").exists())
        self.assertIn("_auth_user_id", self.client.session)

    def test_register_with_bad_data_creates_nothing(self):
        response = self.client.post(reverse("register"), register_data(password2="nope"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 0)

    def test_login_with_correct_credentials(self):
        user, _, _ = make_person()
        response = self.client.post(reverse("login"), {"username": user.email, "password": PASSWORD})
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_with_wrong_password_fails(self):
        user, _, _ = make_person()
        response = self.client.post(reverse("login"), {"username": user.email, "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_with_unknown_email_fails(self):
        response = self.client.post(reverse("login"),
                                    {"username": "nobody@example.com", "password": PASSWORD})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(response.status_code, 200)

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_logout_ends_session(self):
        user, _, _ = make_person()
        self.client.force_login(user)
        self.client.post(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)


# ---------------------------------------------------------------- support circle invitations
class SupportCircleInviteTests(TestCase):
    def setUp(self):
        self.user, self.person, _ = make_person()
        self.client.force_login(self.user)
        self.url = reverse("support_circle")

    def _invite(self, email="friend@example.com"):
        return self.client.post(self.url, {
            "invitee_name": "Friend", "invitee_email": email, "relationship_type": "Friend"})

    def test_invitation_is_created(self):
        self._invite()
        inv = SupportInvitation.objects.get()
        self.assertEqual(inv.person, self.person)
        self.assertEqual(inv.status, SupportInvitation.PENDING)

    def test_cannot_invite_yourself(self):
        self._invite(email=self.user.email)
        self.assertEqual(SupportInvitation.objects.count(), 0)

    def test_duplicate_pending_invitation_rejected(self):
        self._invite()
        self._invite()
        self.assertEqual(SupportInvitation.objects.count(), 1)

    def test_cannot_invite_someone_already_in_circle(self):
        _, designated = make_supporter(email="friend@example.com")
        link(self.person, designated)
        self._invite()
        self.assertEqual(SupportInvitation.objects.count(), 0)

    def test_cancel_invitation(self):
        inv = make_invitation(self.person)
        self.client.post(self.url, {"cancel_invitation": inv.pk})
        inv.refresh_from_db()
        self.assertEqual(inv.status, SupportInvitation.CANCELLED)

    def test_cannot_cancel_someone_elses_invitation(self):
        _, other_person, _ = make_person(email="other@example.com", phone="0799000111")
        inv = make_invitation(other_person)
        response = self.client.post(self.url, {"cancel_invitation": inv.pk})
        self.assertEqual(response.status_code, 404)
        inv.refresh_from_db()
        self.assertEqual(inv.status, SupportInvitation.PENDING)

    def test_remove_support_person(self):
        _, designated = make_supporter()
        support_link = link(self.person, designated)
        self.client.post(reverse("support_remove", args=[support_link.pk]))
        self.assertFalse(SupportLink.objects.filter(pk=support_link.pk).exists())


# ---------------------------------------------------------------- accepting an invitation
class InviteAcceptViewTests(TestCase):
    def setUp(self):
        self.inviter, self.person, _ = make_person()
        self.invitation = make_invitation(self.person, email="friend@example.com")
        self.url = reverse("invite_accept", args=[self.invitation.token])

    def test_unknown_token_returns_404(self):
        response = self.client.get(reverse("invite_accept", args=["not-a-real-token"]))
        self.assertEqual(response.status_code, 404)

    def test_expired_invitation_shows_message(self):
        self.invitation.expires_at = timezone.now() - timedelta(days=1)
        self.invitation.save()
        response = self.client.get(self.url)
        self.assertContains(response, "expired")

    def test_cancelled_invitation_cannot_be_used(self):
        self.invitation.status = SupportInvitation.CANCELLED
        self.invitation.save()
        self.assertContains(self.client.get(self.url), "no longer valid")

    def test_new_visitor_sees_registration_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/invite_register.html")

    def test_existing_account_is_sent_to_login(self):
        make_supporter(email="friend@example.com")
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_full_flow_register_then_accept_links_support_person(self):
        data = register_data()
        data.pop("email")
        # step 1: register through the invitation link
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302)
        supporter = User.objects.get(email="friend@example.com")
        self.assertEqual(supporter.role_name, Role.DESIGNATED_PERSON)
        # step 2: accept
        self.client.post(self.url)
        self.assertTrue(SupportLink.objects.filter(
            person=self.person, designated=supporter.designated_profile).exists())
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, SupportInvitation.ACCEPTED)

    def test_logged_in_matching_supporter_can_accept(self):
        user, designated = make_supporter(email="friend@example.com")
        self.client.force_login(user)
        self.client.post(self.url)
        link_obj = SupportLink.objects.get(person=self.person, designated=designated)
        self.assertEqual(link_obj.relationship_type, "Friend")

    def test_wrong_account_cannot_accept(self):
        user, designated = make_supporter(email="someone.else@example.com")
        self.client.force_login(user)
        response = self.client.post(self.url)
        self.assertContains(response, "different email")
        self.assertFalse(SupportLink.objects.filter(designated=designated).exists())

    def test_person_at_risk_account_cannot_accept(self):
        other, _, _ = make_person(email="friend@example.com", phone="0799000111")
        self.client.force_login(other)
        response = self.client.post(self.url)
        self.assertContains(response, "support person account")
        self.assertEqual(SupportLink.objects.count(), 0)

    def test_accepted_invitation_cannot_be_reused(self):
        user, _ = make_supporter(email="friend@example.com")
        self.client.force_login(user)
        self.client.post(self.url)
        response = self.client.post(self.url)
        self.assertContains(response, "no longer valid")
        self.assertEqual(SupportLink.objects.count(), 1)


# ---------------------------------------------------------------- dashboards
class DashboardTests(TestCase):
    def test_person_dashboard_counts(self):
        user, person, _ = make_person()
        _, designated = make_supporter()
        link(person, designated)
        self.client.force_login(user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["circle_count"], 1)
        self.assertEqual(response.context["hope_count"], 0)
        self.assertFalse(response.context["has_plan"])

    def test_support_dashboard_flags_overdue_person(self):
        user, person, threshold = make_person(days=3)
        threshold.last_login = timezone.now() - timedelta(days=5)
        threshold.save()
        supporter_user, designated = make_supporter()
        link(person, designated)
        self.client.force_login(supporter_user)
        response = self.client.get(reverse("dashboard"))
        row = response.context["rows"][0]
        self.assertTrue(row["overdue"])
        self.assertEqual(row["days"], 5)

    def test_support_dashboard_active_person_not_overdue(self):
        user, person, threshold = make_person(days=3)
        threshold.last_login = timezone.now() - timedelta(hours=2)
        threshold.save()
        supporter_user, designated = make_supporter()
        link(person, designated)
        self.client.force_login(supporter_user)
        row = self.client.get(reverse("dashboard")).context["rows"][0]
        self.assertFalse(row["overdue"])

    def test_support_dashboard_only_shows_own_people(self):
        _, person_a, _ = make_person(email="a@example.com", phone="0711000001")
        _, person_b, _ = make_person(email="b@example.com", phone="0711000002")
        supporter_user, designated = make_supporter()
        link(person_a, designated)
        self.client.force_login(supporter_user)
        rows = self.client.get(reverse("dashboard")).context["rows"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["link"].person, person_a)
