from django.utils import timezone
from botocore.exceptions import ClientError, BotoCoreError
from apps.core.adapters.aws_adapter import AWSAdapter
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.choices import Provider
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
        serializer = CloudCredentialSerializer(data=request.data, context={"request": request})
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

class CloudCredentialTestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            credential = CloudCredential.objects.get(pk=pk, user=request.user)
        except CloudCredential.DoesNotExist:
            return Response({"detail": "자격증명을 찾을수 없습니다"},status=status.HTTP_404_NOT_FOUND)

        if not credential.is_aws:
            return Response({"detail": "현재 AWS만 지원합니다"}, status=status.HTTP_400_BAD_REQUEST)

        adapter = AWSAdapter(
            access_key = credential.aws_access_key_id,
            secret_key = credential.aws_secret_access_key,
            region = credential.aws_default_region or "ap-northeast-2",
        )

        results = {}

        # 권한 테스트
        try:
            adapter.ec2.describe_instances(MaxResults=5)
            results["ec2"] = "OK"
        except ClientError as e:
            results["ec2"] = f"권한 없음: {e.response['Error']['Code']}"
        except BotoCoreError as e:
            results["ec2"] = f"연결 오류: {str(e)}"

        # Cost Explorer 권한 테스트
        try:
            from datetime import datetime, timezone as tz
            now = datetime.now(tz.utc)
            start = now.replace(day=1).strftime("%Y-%m-%d")
            end = now.strftime("%Y-%m-%d")
            if start == end:
                from datetime import timedelta
                prev = now.replace(day=1) - timedelta(days=1)
                start = prev.replace(day=1).strftime("%Y-%m-%d")
                end = prev.strftime("%Y-%m-%d")
            adapter.cost_explorer.get_cost_and_usage(
                TimePeriod={"Start": start, "End": end},
                Granularity="MONTHLY",
                Metrics=["UnblendedCost"],
            )
            results["cost_explorer"] = "OK"
        except ClientError as e:
            results["cost_explorer"] = f"권한 없음: {e.response['Error']['Code']}"
        except BotoCoreError as e:
            results["cost_explorer"] = f"연결 오류: {str(e)}"

        # Compute Optimizer 권한 테스트
        try:
            adapter.compute_optimizer.get_ec2_instance_recommendations(
                instanceArns=[]
            )
            results["compute_optimizer"] = "OK"
        except ClientError as e:
            code = e.response["Error"]["Code"]
            if code in ("AccessDeniedException", "OptInRequiredException"):
                results["compute_optimizer"] = "미활성화 또는 권한 없음 (선택사항)"
            else:
                results["compute_optimizer"] = f"권한 없음: {code}"

        # 검증 결과 저장
        all_required_ok = results.get("ec2") == "OK"
        credential.is_verified = all_required_ok
        credential.last_verified_at = timezone.now()
        credential.verification_error = None if all_required_ok else str(results)
        credential.save(update_fields=["is_verified", "last_verified_at", "verification_error"])

        return Response(results, status=status.HTTP_200_OK)
