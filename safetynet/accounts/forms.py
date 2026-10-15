from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.validators import RegexValidator
from django.db import transaction

from .models import User, Role, PersonAtRisk, DesignatedPerson, SupportInvitation
from wellbeing.models import AlertThreshold

phone_validator = RegexValidator(
    r"^\+?\d{9,15}$", "Enter a valid phone number, for example +254712345678."
)


class RegisterForm(forms.ModelForm):
    # Public registration always creates a Person at Risk.
    ROLE = Role.PERSON_AT_RISK

    phone_no = forms.CharField(max_length=20, validators=[phone_validator])
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone_no", "gender"]

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        data = super().clean()
        if data.get("password1") != data.get("password2"):
            self.add_error("password2", "Passwords do not match.")
        elif data.get("password1") and len(data["password1"]) < 8:
            self.add_error("password1", "Use at least 8 characters.")
        return data

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role, _ = Role.objects.get_or_create(role_name=self.ROLE)
        user.set_password(self.cleaned_data["password1"])
        user.save()
        if self.ROLE == Role.PERSON_AT_RISK:
            person = PersonAtRisk.objects.create(user=user)
            AlertThreshold.objects.create(person=person, inactivity_days=3)
        else:
            DesignatedPerson.objects.create(user=user)
        return user


class InviteRegisterForm(RegisterForm):
    # Used only on the invitation page. Role is assigned automatically.
    ROLE = Role.DESIGNATED_PERSON

    def __init__(self, *args, invitation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.invitation = invitation
        if invitation:
            self.fields["email"].initial = invitation.invitee_email
            self.fields["email"].disabled = True


class SupportInvitationForm(forms.ModelForm):
    class Meta:
        model = SupportInvitation
        fields = ["invitee_name", "invitee_email", "relationship_type"]
        labels = {
            "invitee_name": "Their name",
            "invitee_email": "Their email",
            "relationship_type": "Relationship (for example friend, sister, therapist)",
        }

    def clean_invitee_email(self):
        return self.cleaned_data["invitee_email"].strip().lower()


class EmailLoginForm(AuthenticationForm):
    username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autofocus": True}))