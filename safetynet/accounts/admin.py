from django.contrib import admin
from .models import Role, User, PersonAtRisk, DesignatedPerson, SupportLink

admin.site.register([Role, User, PersonAtRisk, DesignatedPerson, SupportLink])
