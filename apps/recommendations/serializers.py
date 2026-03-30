from rest_framework import serializers


class AuditRequestSerializer(serializers.Serializer):
    inventory_id = serializers.IntegerField(help_text="감사할 인벤토리 ID")


class ConsultChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField()
    history = serializers.ListField(child=serializers.DictField(), default=list)
