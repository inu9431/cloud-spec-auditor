from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.choices import Provider
from apps.core.throttles import SyncThrottle
from apps.inventories.models import UserInventory
from apps.inventories.serializers import UserInventorySerializer
from apps.users.models import CloudCredential


class UserInventoryView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=UserInventorySerializer(many=True))
    def get(self, request):
        inventories = UserInventory.objects.filter(user=request.user, is_active=True)
        serializer = UserInventorySerializer(inventories, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(request=UserInventorySerializer)
    def post(self, request):
        serializer = UserInventorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class InventorySyncView(APIView):
    """
    POST /api/inventories/sync/
    django-q2 비동기 태스크로 큐에 등록하고 즉시 반환.
    실제 수집(EC2 + Cost Explorer + Compute Optimizer) + audit은 워커에서 실행된다.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [SyncThrottle]

    def post(self, request):
        from django_q.tasks import async_task

        credential = CloudCredential.objects.filter(
            user=request.user,
            provider=Provider.AWS,
            is_active=True,
        ).first()
        if not credential:
            return Response(
                {
                    "detail": "등록된 AWS 자격증명이 없습니다. POST /api/users/credentials/ 로 먼저 등록하세요."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        task_id = async_task(
            "pipeline.flows.inventory_flow.sync_user_inventory",
            credential.id,
        )

        return Response(
            {"status": "queued", "task_id": task_id},
            status=status.HTTP_202_ACCEPTED,
        )
