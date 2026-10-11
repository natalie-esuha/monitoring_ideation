from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone

from .forms import RegisterForm
from .models import Role


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