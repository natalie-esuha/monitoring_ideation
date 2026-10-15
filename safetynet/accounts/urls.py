from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import EmailLoginForm

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("register/", views.register, name="register"),
    path("invite/<str:token>/", views.invite_accept, name="invite_accept"),
    path("login/", auth_views.LoginView.as_view(
        template_name="accounts/login.html", authentication_form=EmailLoginForm,
        redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]