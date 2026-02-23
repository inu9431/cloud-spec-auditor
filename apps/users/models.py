from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models

from apps.core.choices import NormalizedRegion, Provider
from apps.core.models import BaseModel


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("이메일은 필수입니다")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(email, password, **extra_fields)


class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    """
    커스텀 사용자 모델

    클라우드 비용 최적화 서비스 사용자 정보를 저장
    3사(AWS, GCP, Azure) 클라우드 연동 정보를 관리
    """

    # 기본정보(AbstractUser 상속)
    email = models.EmailField(
        unique=True,
        help_text="이메일 주소",
    )
    # 추가 프로필 정보
    company_name = models.CharField(max_length=100, blank=True, null=True, help_text="소속 회사명")
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        unique=True,
        help_text="연락처",
    )

    # 기본 정보

    default_provider = models.CharField(
        max_length=10,
        choices=Provider.choices,
        default=Provider.AWS,
        help_text="기본 클라우드 제공자(대시보드 기본값)",
    )
    default_region = models.CharField(
        max_length=10,
        choices=NormalizedRegion.choices,
        default=NormalizedRegion.KR,
        help_text="기본 리전(대시보드 기본값)",
    )
    preferred_currency = models.CharField(
        max_length=3,
        default="USD",
        help_text="기본 통화(USD, KRW 등)",
    )

    # 구독 정보
    is_premium = models.BooleanField(
        default=False,
        help_text="프리미엄 사용자 여부",
    )
    subscription_ends_at = models.DateField(
        null=True,
        blank=True,
        help_text="구독 만료일",
    )

    # 계정 상태
    is_active = models.BooleanField(default=False, help_text="계정 활성화 여부")
    is_staff = models.BooleanField(default=False, help_text="스태프 여부")

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = "users"
        verbose_name = "사용자"
        verbose_name_plural = "사용자 목록"

    def __str__(self):
        return self.email

    # Properties
    @property
    def has_any_credentials(self) -> bool:
        """클라우드 연동 여부 확인(한개라도 있으면 True)"""
        return self.cloud_credentials.filter(is_active=True).exists()

    @property
    def connected_providers(self) -> list[str]:
        """연동된 클라우드 제공자 목록"""
        return list(
            self.cloud_credentials.filter(is_active=True).values_list("provider", flat=True)
        )


class CloudCredential(BaseModel):
    """
    클라우드 인증 정보(AWS, GCP, Azure)

    사용자별로 여러 클라우드 계정을 연동
    인증 정보는 암호화하여 저장
    """

    class CredentialType(models.TextChoices):
        """인증 방식"""

        ACCESS_KEY = "ACCESS_KEY", "Access Key(AWS)"
        SERVICE_ACCOUNT = "SERVICE_ACCOUNT", "Service Account(GCP)"
        SERVICE_PRINCIPAL = "SERVICE_PRINCIPAL", "Service Principal(Azure)"

    # 연결 정보
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="cloud_credentials",
        help_text="연동된 사용자",
    )

    # 클라우드 정보
    provider = models.CharField(
        max_length=10,
        choices=Provider.choices,
        help_text="클라우드 제공자(AWS, GCP, Azure)",
    )
    credential_type = models.CharField(
        max_length=20,
        choices=CredentialType.choices,
        help_text="인증 방식",
    )

    nickname = models.CharField(max_length=50, blank=True, help_text="사용자 지정 별칭")

    # ==================== AWS 인증 정보 ====================
    aws_access_key_id = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="AWS Access Key ID (암호화 필요)",
    )
    aws_secret_access_key = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="AWS Secret Access Key (암호화 필요)",
    )
    aws_default_region = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="AWS 기본 리전 (예: ap-northeast-2)",
    )

    # ==================== GCP 인증 정보 ====================
    gcp_project_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="GCP Project ID",
    )
    gcp_service_account_json = models.TextField(
        blank=True,
        null=True,
        help_text="GCP Service Account JSON (암호화 필요)",
    )

    # ==================== Azure 인증 정보 ====================
    azure_tenant_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Azure Tenant ID",
    )
    azure_client_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Azure Client ID",
    )
    azure_client_secret = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Azure Client Secret (암호화 필요)",
    )
    azure_subscription_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Azure Subscription ID",
    )

    # ==================== 상태 관리 ====================
    is_active = models.BooleanField(
        default=True,
        help_text="활성 상태 (False면 연동 해제)",
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="인증 정보 검증 완료 여부",
    )
    last_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="마지막 검증 시간",
    )
    verification_error = models.TextField(
        blank=True,
        null=True,
        help_text="검증 실패 시 에러 메시지",
    )

    class Meta:
        db_table = "cloud_credentials"
        verbose_name = "클라우드 인증 정보"
        verbose_name_plural = "클라우드 인증 정보 목록"
        indexes = [
            models.Index(fields=["user", "provider"]),
            models.Index(fields=["user", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "provider", "nickname"],
                name="unique_user_provider_nickname",
            )
        ]

    def __str__(self):
        nickname = self.nickname or self.provider
        return f"{self.user.email} - {nickname}"

    # ==================== Properties ====================
    @property
    def is_aws(self) -> bool:
        return self.provider == Provider.AWS

    @property
    def is_gcp(self) -> bool:
        return self.provider == Provider.GCP

    @property
    def is_azure(self) -> bool:
        return self.provider == Provider.AZURE

    @property
    def has_valid_credentials(self) -> bool:
        """필수 인증 정보가 있는지 확인"""
        if self.is_aws:
            return bool(self.aws_access_key_id and self.aws_secret_access_key)
        elif self.is_gcp:
            return bool(self.gcp_project_id and self.gcp_service_account_json)
        elif self.is_azure:
            return bool(
                self.azure_tenant_id
                and self.azure_client_id
                and self.azure_client_secret
                and self.azure_subscription_id
            )
        return False
