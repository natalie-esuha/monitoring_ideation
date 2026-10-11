from django.urls import path
from . import views

urlpatterns = [
    path("safety-plan/", views.safety_plan, name="safety_plan"),
    path("hope-box/", views.hope_box, name="hope_box"),
    path("hope-box/<int:pk>/delete/", views.hope_box_delete, name="hope_box_delete"),
    path("support-circle/", views.support_circle, name="support_circle"),
    path("support-circle/<int:pk>/remove/", views.support_remove, name="support_remove"),
    path("alert-settings/", views.threshold_settings, name="threshold"),
    path("helplines/", views.helplines, name="helplines"),
]