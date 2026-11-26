from django.urls import path
from . import views

urlpatterns = [
    path("safety-plan/", views.safety_plan, name="safety_plan"),
    path("hope-box/", views.hope_box, name="hope_box"),
    path("hope-box/<int:pk>/delete/", views.hope_box_delete, name="hope_box_delete"),
    path("support-circle/", views.support_circle, name="support_circle"),
    path("support-circle/<int:pk>/remove/", views.support_remove, name="support_remove"),
    path("alert-settings/", views.threshold_settings, name="threshold"),
    path("events/", views.events, name="events"),
    path("events/<int:pk>/delete/", views.event_delete, name="event_delete"),
    path("check-in/", views.checkin, name="checkin"),
    path("mood/", views.mood_history, name="mood"),
    path("help-request/", views.help_request, name="help_request"),
    path("helplines/", views.helplines, name="helplines"),
]