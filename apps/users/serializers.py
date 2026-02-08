from django.contrib.auth import get_user_model

from rest_framework import serializers

User = get_user_model()


class UserSignupserializer(serializers.ModelSerializer):
    """회원가입 시리얼라이저"""

    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "username",
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
