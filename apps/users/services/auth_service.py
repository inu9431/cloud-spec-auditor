from django.contrib.auth import get_user_model

from rest_framework import serializers

# from django.core.exceptions import ValidationError
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class AuthService:
    """인증 관련 비즈니스 로직"""

    @staticmethod
    def generate_tokens(user) -> dict:
        """유저 객체로 JWT access/refresh 토큰 생성"""
        refresh = RefreshToken.for_user(user)
        return {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }

    @staticmethod
    def blacklist_token(refresh_token: str) -> None:
        """refresh 토큰을 블랙리스트에 등록(로그아웃)"""
        token = RefreshToken(refresh_token)
        token.blacklist()

    # 회원가입
    @staticmethod
    def signup(validated_data: dict) -> tuple:
        """유저 생성 후 토큰 반환"""
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        tokens = AuthService.generate_tokens(user)
        return user, tokens

    # 로그인
    @staticmethod
    def login(email: str, password: str) -> tuple:
        """이메일 + 비밀번호 검증 후 토큰 반환"""
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise AuthenticationFailed("이메일 또는 비밀번호가 일치하지 않습니다")
        if not user.check_password(password):
            raise AuthenticationFailed("이메일 또는 비밀번호가 일치하지 않습니다")
        if not user.is_active:
            raise AuthenticationFailed("비활성화 된 계정입니다")

        tokens = AuthService.generate_tokens(user)
        return user, tokens
