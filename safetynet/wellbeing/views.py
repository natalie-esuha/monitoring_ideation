from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Avg
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.forms import SupportInvitationForm
from accounts.models import Role, SupportLink, SupportInvitation
from .alerts import run_alert_check, normalize_phone
from .forms import SafetyItemForm, HopeBoxForm, ThresholdForm, EventForm
from .models import SafetyPlan, HopeBoxItem, Event, Alert, MoodCheckIn
from .sms import send_sms


def person_only(view):
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.user.role_name != Role.PERSON_AT_RISK:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


SAFETY_SECTIONS = [
    {"key": "warning_signs", "label": "My warning signs", "icon": "bi-exclamation-triangle", "color": "ic-orange",
     "hint": "Thoughts, moods or behaviours that tell me a crisis may be coming"},
    {"key": "triggers", "label": "Things that trigger hard moments", "icon": "bi-lightning-charge", "color": "ic-pink",
     "hint": "Situations, places or events that make things worse"},
    {"key": "coping_strategy", "label": "Things I can do to cope", "icon": "bi-heart-pulse", "color": "ic-teal",
     "hint": "Walking, music, praying, calling a friend, breathing exercises"},
]


def _plan_lines(text):
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


@person_only
def safety_plan(request):
    person = request.user.person_profile
    plan, _ = SafetyPlan.objects.get_or_create(person=person)
    valid = {s["key"] for s in SAFETY_SECTIONS}
    form = SafetyItemForm()

    if request.method == "POST":
        if request.POST.get("action") == "delete":
            key = request.POST.get("section")
            if key in valid:
                lines = _plan_lines(getattr(plan, key))
                try:
                    idx = int(request.POST.get("index", "x"))
                except ValueError:
                    idx = -1
                if 0 <= idx < len(lines):
                    del lines[idx]
                    setattr(plan, key, "\n".join(lines))
                    plan.save()
                    messages.success(request, "Removed from your safety plan.")
            return redirect("safety_plan")

        form = SafetyItemForm(request.POST)
        if form.is_valid():
            key = form.cleaned_data["section"]
            lines = _plan_lines(getattr(plan, key))
            lines.append(" ".join(form.cleaned_data["text"].split()))
            setattr(plan, key, "\n".join(lines))
            plan.save()
            messages.success(request, "Added to your safety plan.")
            return redirect("safety_plan")

    sections = [dict(s, items=list(enumerate(_plan_lines(getattr(plan, s["key"]))))) for s in SAFETY_SECTIONS]
    return render(request, "wellbeing/safety_plan.html", {"form": form, "sections": sections})


@person_only
def hope_box(request):
    person = request.user.person_profile
    form = HopeBoxForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.person = person
        item.save()
        messages.success(request, "Added to your hope box.")
        return redirect("hope_box")
    items = person.hope_items.order_by("-item_id")
    return render(request, "wellbeing/hope_box.html", {"form": form, "items": items})


@person_only
@require_POST
def hope_box_delete(request, pk):
    item = get_object_or_404(HopeBoxItem, pk=pk, person=request.user.person_profile)
    if item.file_url:
        item.file_url.delete(save=False)
    item.delete()
    messages.success(request, "Item removed.")
    return redirect("hope_box")


@person_only
def support_circle(request):
    person = request.user.person_profile

    # Cancel a pending invitation
    if request.method == "POST" and "cancel_invitation" in request.POST:
        invitation = get_object_or_404(
            SupportInvitation,
            pk=request.POST["cancel_invitation"],
            person=person,
            status=SupportInvitation.PENDING,
        )
        invitation.status = SupportInvitation.CANCELLED
        invitation.save()
        messages.success(request, "Invitation cancelled.")
        return redirect("support_circle")

    form = SupportInvitationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["invitee_email"]
        now = timezone.now()
        if email == request.user.email.lower():
            form.add_error("invitee_email", "You cannot invite yourself.")
        elif SupportLink.objects.filter(person=person, designated__user__email__iexact=email).exists():
            form.add_error("invitee_email", "This person is already in your circle.")
        elif SupportInvitation.objects.filter(
            person=person, invitee_email=email,
            status=SupportInvitation.PENDING, expires_at__gt=now,
        ).exists():
            form.add_error("invitee_email", "There is already a pending invitation for this email.")
        else:
            invitation = form.save(commit=False)
            invitation.person = person
            invitation.save()
            messages.success(request, "Invitation created. Copy the link below and send it to them.")
            return redirect("support_circle")

    links = person.support_links.select_related("designated__user")
    pending = []
    for inv in person.invitations.filter(
        status=SupportInvitation.PENDING, expires_at__gt=timezone.now()
    ).order_by("-created_at"):
        inv.url = request.build_absolute_uri(reverse("invite_accept", args=[inv.token]))
        pending.append(inv)
    return render(request, "wellbeing/support_circle.html",
                  {"form": form, "links": links, "pending": pending})


@person_only
@require_POST
def support_remove(request, pk):
    link = get_object_or_404(SupportLink, pk=pk, person=request.user.person_profile)
    link.delete()
    messages.success(request, "Support person removed.")
    return redirect("support_circle")


@person_only
def threshold_settings(request):
    threshold = request.user.person_profile.threshold
    form = ThresholdForm(request.POST or None, instance=threshold)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Alert setting updated.")
        return redirect("threshold")
    return render(request, "wellbeing/threshold.html", {"form": form})


@person_only
def events(request):
    form = EventForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        event = form.save(commit=False)
        event.user = request.user
        event.save()
        if event.type == Event.TRIGGER:
            run_alert_check()
        messages.success(request, "Event added.")
        return redirect("events")
    today = timezone.localdate()
    upcoming = request.user.events.filter(date__gte=today).order_by("date")
    past = request.user.events.filter(date__lt=today).order_by("-date")[:10]
    return render(request, "wellbeing/events.html",
                  {"form": form, "upcoming": upcoming, "past": past})


@person_only
@require_POST
def event_delete(request, pk):
    event = get_object_or_404(Event, pk=pk, user=request.user)
    event.delete()
    messages.success(request, "Event removed.")
    return redirect("events")


@person_only
@require_POST
def checkin(request):
    try:
        mood = int(request.POST.get("mood", ""))
    except ValueError:
        mood = 0
    if mood not in dict(MoodCheckIn.MOODS):
        messages.error(request, "Please tap one of the faces.")
        return redirect("dashboard")
    note = request.POST.get("note", "").strip()[:255]
    MoodCheckIn.objects.update_or_create(
        person=request.user.person_profile,
        date=timezone.localdate(),
        defaults={"mood": mood, "note": note},
    )
    messages.success(request, "Thanks for checking in today.")
    return redirect("dashboard")


@person_only
def mood_history(request):
    person = request.user.person_profile
    today = timezone.localdate()
    days = 30
    start = today - timedelta(days=days - 1)
    qs = person.checkins.filter(date__gte=start)
    by_date = {c.date: c for c in qs}

    columns = []
    for i in range(days):
        d = start + timedelta(days=i)
        c = by_date.get(d)
        columns.append({
            "date": d,
            "mood": c.mood if c else None,
            "label": c.label if c else "No check-in",
            "height": c.mood * 20 if c else 0,
        })
    entries = list(qs.order_by("-date")[:14])
    average = qs.aggregate(avg=Avg("mood"))["avg"]
    return render(request, "wellbeing/mood.html", {
        "columns": columns, "entries": entries, "average": average,
        "count": len(by_date), "days": days, "start": start, "today": today,
    })


@person_only
@require_POST
def help_request(request):
    person = request.user.person_profile
    threshold = person.threshold
    links = list(person.support_links.select_related("designated__user"))
    if not links:
        messages.warning(request, "You have no one in your support circle yet. Please call one of the helplines below now, "
                                  "and add a support person when you can.")
        return redirect("helplines")

    now = timezone.now()
    recent = Alert.objects.filter(
        threshold=threshold, kind=Alert.HELP, date_sent__gte=now - timedelta(minutes=10)
    ).exclude(delivery_status="failed").exists()
    if recent:
        messages.info(request, "Your support circle was already told a few minutes ago. They know you need help.")
        return redirect("helplines")

    name = request.user.first_name
    for link in links:
        supporter = link.designated.user
        body = (f"SafetyNet: {name} has asked for help right now. "
                f"Please call or visit them as soon as you can.")
        status = send_sms(normalize_phone(supporter.phone_no), body)
        Alert.objects.create(threshold=threshold, designated=link.designated,
                             kind=Alert.HELP, delivery_status=status)
    messages.success(request, "Your support circle has been told you need help. "
                              "If you are in danger, call 999 or one of the helplines below now.")
    return redirect("helplines")


def helplines(request):
    lines = [
        {"name": "Befrienders Kenya", "detail": "Emotional support, free and confidential", "phone": "+254722178177"},
        {"name": "Kenya Red Cross", "detail": "Free counselling hotline", "phone": "1199"},
        {"name": "Niskize", "detail": "Mental health support line", "phone": "0900620800"},
    ]
    return render(request, "wellbeing/helplines.html", {"lines": lines})