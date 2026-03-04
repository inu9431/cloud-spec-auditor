from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.models import CloudCredential
from apps.users.serializers import (
    CloudCredentialResponseSerializer,
    CloudCredentialSerializer,
    IAMCSVUploadSerializer,
    LoginSerializer,
    LogoutSerializer,
    UserResponseSerializer,
    UserSignupserializer,
)
from apps.users.services.auth_service import AuthService
from apps.core.choices import Provider


class SignupView(APIView):
    """회원가입 뷰"""

    permission_classes = [AllowAny]
    serializer_class = UserSignupserializer

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
    serializer_class = LoginSerializer

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
    serializer_class = LogoutSerializer

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        AuthService.blacklist_token(serializer.validated_data["refresh"])

        return Response(status=status.HTTP_205_RESET_CONTENT)


class CloudCredentialView(APIView):
    """AWS Key 직접 입력 등록 및 목록 조회"""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        credentials = CloudCredential.objects.filter(user=request.user, is_active=True)
        serializer = CloudCredentialResponseSerializer(credentials, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = CloudCredentialSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        credential = serializer.save()
        return Response(
            CloudCredentialResponseSerializer(credential).data,
            status=status.HTTP_201_CREATED,
        )


class CloudCredentialCSVView(APIView):
    """AWS IAM CSV 파일 업로드로 Key 등록"""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = IAMCSVUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        parsed = serializer.parse_csv()
        nickname = serializer.validated_data.get("nickname", "")
        region = serializer.validated_data.get("aws_default_region", "ap-northeast-2")

        credential = CloudCredential.objects.create(
            user=request.user,
            provider=Provider.AWS,
            credential_type=CloudCredential.CredentialType.ACCESS_KEY,
            nickname=nickname,
            aws_access_key_id=parsed["access_key_id"],
            aws_secret_access_key=parsed["secret_access_key"],
            aws_default_region=region,
        )
        return Response(
            CloudCredentialResponseSerializer(credential).data,
            status=status.HTTP_201_CREATED,
        )
