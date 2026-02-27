from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.costs.serializers import (
    AWSSyncRequestSerializer,
    AzureSyncRequestSerializer,
    GCPSyncRequestSerializer,
    InstanceCompareRequestSerializer,
)
from apps.costs.services.compare_service import InstanceCompareService
from apps.costs.services.price_sync_service import PriceSyncService


class AzurePriceSyncView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=AzureSyncRequestSerializer)
    def post(self, request):
        region = request.data.get("region", "koreacentral")
        service = PriceSyncService()
        service.sync_azure_prices(region)
        return Response({"message": f"{region} 가격 동기화 완료"}, status=status.HTTP_200_OK)


class AWSPriceSyncView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=AWSSyncRequestSerializer)
    def post(self, request):
        region = request.data.get("region", "ap-northeast-2")
        service = PriceSyncService()
        service.sync_aws_prices(region)
        return Response({"message": f"{region} 가격 동기화 완료"}, status=status.HTTP_200_OK)


class GCPPriceSyncView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=GCPSyncRequestSerializer)
    def post(self, request):
        region = request.data.get("region", "asia-northeast3")
        service = PriceSyncService()
        service.sync_gcp_prices(region)
        return Response({"message": f"{region} 가격 동기화 완료"}, status=status.HTTP_200_OK)


class InstanceCompareView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(parameters=[InstanceCompareRequestSerializer])
    def get(self, request):
        serializer = InstanceCompareRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        service = InstanceCompareService()

        if data.get("instance_type"):
            result = service.compare_by_instance_type(
                instance_type=data["instance_type"],
                region_normalized=data.get("region_normalized"),
            )
        else:
            result = service.compare_by_spec(
                vcpu=data["vcpu"],
                memory_gb=data["memory_gb"],
                region_normalized=data.get("region_normalized"),
            )
        return Response(result, status=status.HTTP_200_OK)
