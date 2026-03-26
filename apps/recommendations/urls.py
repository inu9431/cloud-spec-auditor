from django.urls import path

from apps.recommendations.views import AuditView, ConsultView, ConsultChatView

urlpatterns = [
    path("audit/", AuditView.as_view(), name="audit"),
    path("consult/", ConsultView.as_view(), name="consult"),
    path("consult/chat/", ConsultChatView.as_view(), name="consult-chat"),
]
