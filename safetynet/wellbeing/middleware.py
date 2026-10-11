from datetime import timedelta
from django.db.models import Q
from django.utils import timezone

from accounts.models import Role
from .models import AlertThreshold


class ActivityMiddleware:
    """Records the last time a person at risk used the app (at most once every 5 minutes)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and user.role_name == Role.PERSON_AT_RISK:
            now = timezone.now()
            AlertThreshold.objects.filter(person_id=user.pk).filter(
                Q(last_login__isnull=True) | Q(last_login__lt=now - timedelta(minutes=5))
            ).update(last_login=now)
        return self.get_response(request)