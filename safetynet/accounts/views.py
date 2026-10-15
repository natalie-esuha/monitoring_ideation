from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone

from .forms import RegisterForm, InviteRegisterForm
from .models import Role, SupportInvitation, SupportLink, User


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Welcome. Your account has been created.")
        return redirect("dashboard")
    return render(request, "accounts/register.html", {"form": form})


def invite_accept(request, token):
    invitation = get_object_or_404(
        SupportInvitation.objects.select_related("person__user"), token=token
    )

    def invalid(reason):
        return render(request, "accounts/invite_invalid.html", {"reason": reason})

    if not invitation.is_usable:
        return invalid("This invitation has expired or is no longer valid.")

    inviter = invitation.person.user

    if request.user.is_authenticated:
        user = request.user
        if user.email.lower() != invitation.invitee_email:
            return invalid("This invitation was sent to a different email address. "
                           "Log out and open the link again with the right account.")
        if user.role_name != Role.DESIGNATED_PERSON:
            return invalid("This invitation can only be accepted by a support person account.")
        if request.method == "POST":
            with transaction.atomic():
                SupportLink.objects.get_or_create(
                    person=invitation.person,
                    designated=user.designated_profile,
                    defaults={"relationship_type": invitation.relationship_type},
                )
                invitation.status = SupportInvitation.ACCEPTED
                invitation.save()
            messages.success(request, f"You are now a support person for {inviter.first_name}.")
            return redirect("dashboard")
        return render(request, "accounts/invite_accept.html",
                      {"invitation": invitation, "inviter": inviter})

    # Not logged in
    if User.objects.filter(email__iexact=invitation.invitee_email).exists():
        messages.info(request, "Log in to accept this invitation.")
        return redirect(f"{reverse('login')}?next={request.path}")

    form = InviteRegisterForm(request.POST or None, invitation=invitation)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your support person account has been created.")
        return redirect("invite_accept", token=token)
    return render(request, "accounts/invite_register.html",
                  {"form": form, "invitation": invitation, "inviter": inviter})


@login_required
def dashboard(request):
    user = request.user
    if user.role_name == Role.DESIGNATED_PERSON:
        now = timezone.now()
        links = user.designated_profile.supported.select_related("person__user", "person__threshold")
        rows = []
        for link in links:
            threshold = getattr(link.person, "threshold", None)
            last = threshold.last_login if threshold else None
            days = (now - last).days if last else None
            limit = threshold.inactivity_days if threshold else None
            rows.append({
                "link": link,
                "last": last,
                "days": days,
                "limit": limit,
                "overdue": days is not None and limit is not None and days >= limit,
            })
        return render(request, "accounts/dashboard_designated.html", {"rows": rows})
    if user.role_name == Role.PERSON_AT_RISK:
        person = user.person_profile
        context = {
            "circle_count": person.support_links.count(),
            "hope_count": person.hope_items.count(),
            "has_plan": hasattr(person, "safety_plan"),
        }
        return render(request, "accounts/dashboard_person.html", context)
    return redirect("admin:index")