from rest_framework import serializers

from apps.inventories.models import UserInventory


class UserInventorySerializer(serializers.ModelSerializer):
    cost_data_notice = serializers.SerializerMethodField()

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
            "cost_updated_at",
            "cost_data_notice",
        ]

    def get_cost_data_notice(self, obj):
        if obj.cost_updated_at:
            return "비용 데이터는 AWS Cost Explorer 기준이며 최대 24시간 지연될 수 있습니다."
        return None
