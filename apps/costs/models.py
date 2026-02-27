from django.contrib.admin.utils import help_text_for_field
from django.db import models

from apps.core.choices import NormalizedRegion, Provider
from apps.core.models import BaseModel
from apps.costs.choices import ConfidenceLevel, PricingModel, PricingSource


class CloudService(BaseModel):
    """클라우드 API 서비스 상품 정보"""

    # 기본 정보
    provider = models.CharField(
        max_length=10, choices=Provider.choices, help_text="클라우드 제공자(AWS, GCP, Azure)"
    )
    instance_type = models.CharField(max_length=50, help_text="인스턴스 유형")
    region = models.CharField(
        max_length=50, default="us-east-1", help_text="클라우드 provider 원본 리전"
    )
    region_normalized = models.CharField(
        max_length=20,
        choices=NormalizedRegion.choices,
        null=True,
        blank=True,
        help_text="표준화된 리전 코드",
    )

    # 스펙
    vcpu = models.IntegerField(help_text="가상환경 컴퓨팅 CPU")
    memory_gb = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="가상환경 컴퓨팅 메모리 용량"
    )
    storage_gb = models.IntegerField(
        null=True, blank=True, help_text="가상환경 컴퓨팅 스토리지 용량"
    )

    # 가격 정보
    currency = models.CharField(max_length=50, default="USD", help_text="통합코드")
    price_per_hour = models.DecimalField(
        max_digits=10, decimal_places=4, help_text="클라우드 서비스 시간당 지불 비용"
    )
    pricing_model = models.CharField(
        max_length=20, choices=PricingModel.choices, help_text="가격모델"
    )
    pricing_source = models.CharField(
        max_length=20, choices=PricingSource.choices, help_text="가격 데이터 출처"
    )

    # 메타 정보
    confidence_level = models.CharField(
        max_length=20,
        choices=ConfidenceLevel.choices,
        default=ConfidenceLevel.MEDIUM,
        help_text="가격 신뢰도",
    )
    last_verified_at = models.DateField(help_text="공식 api를 통해 검증된 마지막 가격정보 갱신시간")
    is_active = models.BooleanField(default=True, help_text=("활성화 상태"))

    class Meta:
        db_table = "cloud_services"
        indexes = [
            models.Index(fields=["provider", "instance_type"]),
            models.Index(fields=["vcpu", "memory_gb"]),
            models.Index(fields=["region_normalized"]),
            models.Index(fields=["pricing_model"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "instance_type", "region", "pricing_model"],
                name="unique_cloud_service",
            ),
        ]
        ordering = ["provider", "price_per_hour"]

    def __str__(self):
        return (
            f"{self.provider} - {self.instance_type} "
            f"(${self.region} - ${self.price_per_hour}/hr)"
        )

    @property
    def price_per_month(self):
        """
        월 730 기준 예상 비용
        """
        return self.price_per_hour * 730
