from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from accounts.models import Role, SupportLink
from .forms import SafetyPlanForm, HopeBoxForm, ThresholdForm, SupportLinkForm
from .models import SafetyPlan, HopeBoxItem


def person_only(view):
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if request.user.role_name != Role.PERSON_AT_RISK:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


@person_only
def safety_plan(request):
    person = request.user.person_profile
    plan, _ = SafetyPlan.objects.get_or_create(person=person)
    form = SafetyPlanForm(request.POST or None, instance=plan)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your safety plan has been saved.")
        return redirect("safety_plan")
    return render(request, "wellbeing/safety_plan.html", {"form": form})


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
    form = SupportLinkForm(request.POST or None, person=person)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Support person added to your circle.")
        return redirect("support_circle")
    links = person.support_links.select_related("designated__user")
    return render(request, "wellbeing/support_circle.html", {"form": form, "links": links})


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


def helplines(request):
    lines = [
        {"name": "Befrienders Kenya", "detail": "Emotional support, free and confidential", "phone": "+254722178177"},
        {"name": "Kenya Red Cross", "detail": "Free counselling hotline", "phone": "1199"},
        {"name": "Niskize", "detail": "Mental health support line", "phone": "0900620800"},
    ]
    return render(request, "wellbeing/helplines.html", {"lines": lines})