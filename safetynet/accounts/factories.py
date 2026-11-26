"""Helpers for building test data. Used by accounts/tests.py and wellbeing/tests.py."""
from accounts.models import (
    Role, User, PersonAtRisk, DesignatedPerson, SupportLink, SupportInvitation,
)
from wellbeing.models import AlertThreshold

PASSWORD = "StrongPass123"


def _role(name):
    return Role.objects.get_or_create(role_name=name)[0]


def make_person(email="person@example.com", phone="0712345678", days=3, first_name="Pat"):
    """Returns (user, person_at_risk, threshold)."""
    user = User.objects.create_user(
        email=email, password=PASSWORD, first_name=first_name, last_name="Person",
        phone_no=phone, gender="Female", role=_role(Role.PERSON_AT_RISK),
    )
    person = PersonAtRisk.objects.create(user=user)
    threshold = AlertThreshold.objects.create(person=person, inactivity_days=days)
    return user, person, threshold


def make_supporter(email="support@example.com", phone="0722000111", first_name="Sam"):
    """Returns (user, designated_person)."""
    user = User.objects.create_user(
        email=email, password=PASSWORD, first_name=first_name, last_name="Supporter",
        phone_no=phone, gender="Male", role=_role(Role.DESIGNATED_PERSON),
    )
    return user, DesignatedPerson.objects.create(user=user)


def link(person, designated, relationship="Friend"):
    return SupportLink.objects.create(person=person, designated=designated,
                                      relationship_type=relationship)


def make_invitation(person, email="friend@example.com", name="Friend"):
    return SupportInvitation.objects.create(
        person=person, invitee_name=name, invitee_email=email, relationship_type="Friend",
    )