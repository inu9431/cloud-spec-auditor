import csv
import io

from django.contrib.auth import get_user_model

from rest_framework import serializers

from apps.users.models import CloudCredential
from apps.core.choices import Provider

User = get_user_model()


class UserSignupserializer(serializers.ModelSerializer):
    """회원가입 시리얼라이저"""

    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "password_confirm",
            "company_name",
            "phone_number",
        ]

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "비밀번호가 일치하지 않습니다."})
        return attrs


class LoginSerializer(serializers.Serializer):
    """로그인 시리얼라이저"""

    email = serializers.EmailField()
    password = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    """로그아웃 시리얼라이저"""

    refresh = serializers.CharField()


class UserResponseSerializer(serializers.ModelSerializer):
    """응답용 유저 시리얼라이저 (비번제외)"""

    class Meta:
        model = User
        fields = ["id", "email", "company_name", "phone_number"]


class CloudCredentialSerializer(serializers.ModelSerializer):
    """AWS Key 직접 입력용 시리얼라이저"""

    class Meta:
        model = CloudCredential
        fields = [
            "id",
            "provider",
            "credential_type",
            "nickname",
            "aws_access_key_id",
            "aws_secret_access_key",
            "aws_default_region",
            "is_active",
        ]
        extra_kwargs = {
            "aws_secret_access_key": {"write_only": True},
        }

    def validate(self, attrs):
        provider = attrs.get("provider", Provider.AWS)
        if provider == Provider.AWS:
            if not attrs.get("aws_access_key_id") or not attrs.get("aws_secret_access_key"):
                raise serializers.ValidationError("AWS Key ID와 Secret Key는 필수입니다.")
        return attrs

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        validated_data.setdefault("credential_type", CloudCredential.CredentialType.ACCESS_KEY)
        return super().create(validated_data)


class CloudCredentialResponseSerializer(serializers.ModelSerializer):
    """인증 정보 조회용 (Secret Key 제외)"""

    class Meta:
        model = CloudCredential
        fields = [
            "id",
            "provider",
            "credential_type",
            "nickname",
            "aws_access_key_id",
            "aws_default_region",
            "is_active",
            "is_verified",
            "last_verified_at",
        ]


class IAMCSVUploadSerializer(serializers.Serializer):
    """AWS IAM CSV 파일 업로드용 시리얼라이저"""

    csv_file = serializers.FileField()
    nickname = serializers.CharField(max_length=50, required=False, default="")
    aws_default_region = serializers.CharField(max_length=50, required=False, default="ap-northeast-2")

    def validate_csv_file(self, value):
        if not value.name.endswith(".csv"):
            raise serializers.ValidationError("CSV 파일만 업로드 가능합니다.")
        return value

    def parse_csv(self) -> dict:
        """AWS IAM CSV에서 Access Key ID / Secret Access Key 추출"""
        csv_file = self.validated_data["csv_file"]
        content = csv_file.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(content))
        rows = list(reader)
        if not rows:
            raise serializers.ValidationError("CSV 파일이 비어 있습니다.")
        row = rows[0]
        access_key = row.get("Access key ID") or row.get("AccessKeyId", "")
        secret_key = row.get("Secret access key") or row.get("SecretAccessKey", "")
        if not access_key or not secret_key:
            raise serializers.ValidationError(
                "CSV에서 Access Key ID / Secret access key 컬럼을 찾을 수 없습니다."
            )
        return {"access_key_id": access_key, "secret_access_key": secret_key}
