import os
from django import forms

from accounts.models import User, Role, SupportLink
from .models import SafetyPlan, HopeBoxItem, AlertThreshold


class BootstrapMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs["class"] = css


class SafetyPlanForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = SafetyPlan
        fields = ["warning_signs", "triggers", "coping_strategy"]
        labels = {
            "warning_signs": "My warning signs",
            "triggers": "Things that trigger hard moments",
            "coping_strategy": "Things I can do to cope",
        }
        widgets = {
            "warning_signs": forms.Textarea(attrs={"rows": 4, "placeholder": "Thoughts, moods or behaviours that tell me a crisis may be coming"}),
            "triggers": forms.Textarea(attrs={"rows": 4, "placeholder": "Situations, places or events that make things worse"}),
            "coping_strategy": forms.Textarea(attrs={"rows": 4, "placeholder": "Walking, music, praying, calling a friend, breathing exercises"}),
        }


class HopeBoxForm(BootstrapMixin, forms.ModelForm):
    TYPES = [("Photo", "Photo"), ("Note", "Note to myself"), ("Memory", "Memory"),
             ("Reason", "Reason to live"), ("Other", "Other")]
    ALLOWED = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".mp3", ".mp4"}
    MAX_MB = 5

    item_type = forms.ChoiceField(choices=TYPES, label="Type")

    class Meta:
        model = HopeBoxItem
        fields = ["title", "item_type", "file_url"]
        labels = {"title": "Title or message", "file_url": "File (optional)"}

    def clean_file_url(self):
        f = self.cleaned_data.get("file_url")
        if f and hasattr(f, "size"):
            if os.path.splitext(f.name)[1].lower() not in self.ALLOWED:
                raise forms.ValidationError("Allowed files: images, PDF, MP3, MP4.")
            if f.size > self.MAX_MB * 1024 * 1024:
                raise forms.ValidationError(f"File must be under {self.MAX_MB} MB.")
        return f


class ThresholdForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = AlertThreshold
        fields = ["inactivity_days"]
        labels = {"inactivity_days": "Alert my support people after this many days without activity"}
        widgets = {"inactivity_days": forms.NumberInput(attrs={"min": 1, "max": 30})}

    def clean_inactivity_days(self):
        days = self.cleaned_data["inactivity_days"]
        if not 1 <= days <= 30:
            raise forms.ValidationError("Choose a number between 1 and 30.")
        return days


class SupportLinkForm(BootstrapMixin, forms.Form):
    RELATIONSHIPS = [("Family member", "Family member"), ("Friend", "Friend"),
                     ("Therapist", "Therapist"), ("Counsellor", "Counsellor"), ("Other", "Other")]

    email = forms.EmailField(label="Support person's email")
    relationship_type = forms.ChoiceField(choices=RELATIONSHIPS, label="Relationship")

    def __init__(self, *args, person=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.person = person
        self.designated = None

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        try:
            user = User.objects.get(email__iexact=email, role__role_name=Role.DESIGNATED_PERSON)
        except User.DoesNotExist:
            raise forms.ValidationError(
                "No support account was found with this email. Ask them to register first "
                "as someone who supports others."
            )
        if SupportLink.objects.filter(person=self.person, designated=user.designated_profile).exists():
            raise forms.ValidationError("This person is already in your support circle.")
        self.designated = user.designated_profile
        return email

    def save(self):
        return SupportLink.objects.create(
            person=self.person,
            designated=self.designated,
            relationship_type=self.cleaned_data["relationship_type"],
        )