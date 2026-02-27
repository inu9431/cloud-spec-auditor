from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.inventories.models import UserInventory
from apps.inventories.serializers import UserInventorySerializer


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
