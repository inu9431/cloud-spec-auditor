from django.urls import path

from apps.users.views import (
    CloudCredentialCSVView,
    CloudCredentialView,
    LoginView,
    LogoutView,
    SignupView,
)

urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("credentials/", CloudCredentialView.as_view(), name="credentials"),
    path("credentials/csv/", CloudCredentialCSVView.as_view(), name="credentials-csv"),
]
