from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers import (
    LoginSerializer,
    LogoutSerializer,
    UserResponseSerializer,
    UserSignupserializer,
)
from apps.users.services.auth_service import AuthService


class SignupView(APIView):
    """회원가입 뷰"""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserSignupserializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user, tokens = AuthService.signup(serializer.validated_data)

        return Response(
            {
                "user": UserResponseSerializer(user).data,
                "tokens": tokens,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """로그인 뷰"""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user, tokens = AuthService.login(
            serializer.validated_data["email"],
            serializer.validated_data["password"],
        )

        return Response(
            {
                "user": UserResponseSerializer(user).data,
                "tokens": tokens,
            },
            status=status.HTTP_200_OK,
        )


class LogoutView(APIView):
    """로그아웃 뷰"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        AuthService.blacklist_token(serializer.validated_data["refresh"])

        return Response(status=status.HTTP_205_RESET_CONTENT)
