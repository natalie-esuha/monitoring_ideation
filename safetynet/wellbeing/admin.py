from django.contrib import admin
from .models import Event, SafetyPlan, HopeBoxItem, AlertThreshold, Alert

admin.site.register([Event, SafetyPlan, HopeBoxItem, AlertThreshold, Alert])