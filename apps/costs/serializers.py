from rest_framework import serializers


class AzureSyncRequestSerializer(serializers.Serializer):
    region = serializers.CharField(
        default="koreacentral", help_text="Azure 리전명 (예: koreacentral)"
    )


class AWSSyncRequestSerializer(serializers.Serializer):
    region = serializers.CharField(
        default="ap-northeast-2", help_text="AWS 리전명 (예: ap-northeast-2)"
    )


class GCPSyncRequestSerializer(serializers.Serializer):
    region = serializers.CharField(
        default="asia-northeast3", help_text="GCP 리전명 (예: asia-northeast3)"
    )


class InstanceCompareRequestSerializer(serializers.Serializer):
    instance_type = serializers.CharField(required=False, help_text="인스턴스 타입")
    vcpu = serializers.IntegerField(required=False, help_text="vCPU 수")
    memory_gb = serializers.DecimalField(
        required=False, max_digits=10, decimal_places=2, help_text="메모리 (GB)"
    )
    region_normalized = serializers.CharField(required=False, help_text="정규화 리전")

    def validate(self, data):
        if not data.get("instance_type") and not (data.get("vcpu") and data.get("memory_gb")):
            raise serializers.ValidationError(
                "instance_type 또는 vcpu + memory_gb 중 하나는 필수입니다"
            )
        return data
