from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.recommendations.serializers import AuditRequestSerializer
from apps.recommendations.services.audit_service import AuditService

class AuditView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=AuditRequestSerializer)
    def post(self, request):
        serializer = AuditRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = AuditService().audit(
            inventory_id = serializer.validated_data["inventory_id"],
            user = request.user,
        )

        if "error" in result:
            return Response(result, status=status.HTTP_404_NOT_FOUND)
        return Response(result, status=status.HTTP_200_OK)