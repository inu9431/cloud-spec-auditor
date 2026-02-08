from django.contrib.auth import get_user_model
from django.db import models

from apps.core.choices import NormalizedRegion, Provider
from apps.core.models import BaseModel

User = get_user_model()


class UserInventory(BaseModel):
    """
    사용자가 현재 사용중인 클라우드 리소스

    CSV 업로드 또는 Cloudwatch 연동을 통해 수집된
    사용자의 실제 인프라 현황을 저장
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="inventories",
        help_text="이 리소스를 소유한 사용자",
    )

    # 리소스 기본 정보
    provider = models.CharField(
        max_length=10, choices=Provider.choices, help_text="클라우드 제공자(AWS, GCP, AZURE)"
    )
    resource_id = models.CharField(max_length=100, help_text="클라우드 내 고유 리소스 ID")
    instance_type = models.CharField(max_length=50, help_text="인스턴스 유형")

    # 리전 정보
    region = models.CharField(max_length=50, help_text="Provider 원본 리전명")
    region_normalized = models.CharField(
        max_length=10, choices=NormalizedRegion.choices, help_text="정규화된 리전명"
    )

    # 스펙 정보
    vcpu = models.IntegerField(help_text="가상 CPU 코어 수")
    memory_gb = models.DecimalField(max_digits=6, decimal_places=2, help_text="메모리 용량(GB)")
    storage_gb = models.IntegerField(null=True, blank=True, help_text="스토리지 용량(GB)")

    # 실제 사용률
    cpu_usage_avg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="최근 7일 평균 CPU 사용률 (%) - 과스펙 판단 기준",
    )
    memory_usage_avg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="최근 7일 평균 메모리 사용률 (%)",
    )

    # 비용 정보
    current_monthly_cost = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="USD", help_text="통화 코드")

    # 상태 정보
    is_active = models.BooleanField(default=True, help_text="활성 상태")

    class Meta:
        db_table = "user_inventories"
        ordering = ["-created_at"]
        indexes = [
            # 사용자별 활성 리소스 조회 최적화
            models.Index(fields=["user", "is_active"]),
            # Provider + 인스턴스 타입 검색 최적화
            models.Index(fields=["provider", "instance_type"]),
            # 3사 비교 쿼리 최적화
            models.Index(fields=["region_normalized"]),
        ]
        constraints = [
            # 같은 사용자가 동일 리소스 중복 등록 방지
            models.UniqueConstraint(
                fields=["user", "provider", "resource_id"], name="unique_user_resource"
            ),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.provider} {self.instance_type}"

    @property
    def is_over_provisioned(self) -> bool | None:
        """과다 스펙 여부(CPU 30% 미만)"""
        if self.cpu_usage_avg is not None:
            return self.cpu_usage_avg < 30
        return None

    @property
    def is_under_utilized(self) -> bool | None:
        """과소 사용 여부(CPU 10% 미만)"""
        if self.cpu_usage_avg is not None:
            return self.cpu_usage_avg > 10
        return None
