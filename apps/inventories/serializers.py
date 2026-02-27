from rest_framework import serializers
from apps.inventories.models import UserInventory

class UserInventorySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserInventory
        fields = [
            "id",
            "provider",
            "resource_id",
            "instance_type",
            "region",
            "region_normalized",
            "vcpu",
            "memory_gb",
            "storage_gb",
            "cpu_usage_avg",
            "memory_usage_avg",
            "current_monthly_cost",
            "currency",
            "is_active",
        ]