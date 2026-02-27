from django.urls import path

from apps.recommendations.views import AuditView

urlpatterns = [
    path("audit/", AuditView.as_view(), name="audit"),
]
