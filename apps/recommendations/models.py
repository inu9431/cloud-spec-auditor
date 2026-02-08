from django.conf import settings
from django.db import models

from apps.core.choices import Provider
from apps.core.models import BaseModel
from apps.costs.models import CloudService
from apps.inventories.models import UserInventory


class Recommendation(BaseModel):
    """
    AI가 생성한 전체 추천 결과

    사용자의 특정 인벤토리(리소스)에 대한 비용 진단 결과를 저장합니다.
    하나의 Recommendation은 여러 RecommendationItem(대안)을 가질 수 있습니다.
    """

    class Status(models.TextChoices):
        """진단 상태"""

        PENDING = "PENDING", "분석 중"
        COMPLETED = "COMPLETED", "완료"
        FAILED = "FAILED", "실패"

    # ==================== 연결 정보 ====================
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recommendations",
        help_text="추천을 요청한 사용자",
    )
    inventory = models.ForeignKey(
        UserInventory,
        on_delete=models.CASCADE,
        related_name="recommendations",
        help_text="진단 대상 인벤토리 (어떤 리소스에 대한 진단인지)",
    )

    # ==================== 진단 상태 ====================
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text="진단 처리 상태",
    )

    # ==================== 비용 요약 ====================
    total_current_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="현재 월 비용 (진단 시점 스냅샷)",
    )
    total_optimized_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="최적화 후 예상 월 비용",
    )
    total_savings = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="총 예상 절감액 (current - optimized)",
    )
    savings_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="절감률 (%) - save() 시 자동 계산",
    )

    # ==================== AI 진단 결과 ====================
    diagnosis_summary = models.TextField(
        help_text="AI가 생성한 진단 요약 메시지",
    )

    class Meta:
        db_table = "recommendations"
        ordering = ["-created_at"]
        indexes = [
            # 사용자별 진단 이력 조회
            models.Index(fields=["user", "status"]),
            # 인벤토리별 진단 이력 조회
            models.Index(fields=["inventory"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.inventory.instance_type} - ${self.total_savings} 절감"

    def save(self, *args, **kwargs):
        """저장 시 절감률 자동 계산"""
        if self.total_current_cost and self.total_current_cost > 0:
            self.savings_percentage = (self.total_savings / self.total_current_cost) * 100
        super().save(*args, **kwargs)


class RecommendationItem(BaseModel):
    """
    개별 추천 항목 (Recommendation ↔ CloudService 매핑)

    하나의 진단(Recommendation)에 대해 여러 대안을 제시합니다.
    예: "AWS t3.xlarge → AWS t3.medium" 또는 "AWS → GCP 전환"
    """

    class RecommendationType(models.TextChoices):
        """추천 유형"""

        DOWNSIZE = "DOWNSIZE", "다운사이징 (스펙 축소)"
        SWITCH_PROVIDER = "SWITCH_PROVIDER", "프로바이더 변경 (타사 전환)"
        SWITCH_PRICING = "SWITCH_PRICING", "가격 모델 변경 (Spot/Reserved)"
        RIGHTSIZING = "RIGHTSIZING", "적정 사이징"
        NO_ACTION = "NO_ACTION", "현행 유지 권장"

    # ==================== 연결 정보 ====================
    recommendation = models.ForeignKey(
        Recommendation,
        on_delete=models.CASCADE,
        related_name="items",
        help_text="상위 추천 결과",
    )
    recommended_service = models.ForeignKey(
        CloudService,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendation_items",
        help_text="추천하는 CloudService (삭제되어도 Item 유지)",
    )

    # ==================== 추천 유형 ====================
    recommendation_type = models.CharField(
        max_length=20,
        choices=RecommendationType.choices,
        help_text="추천 유형 (다운사이징, 프로바이더 변경 등)",
    )

    # ==================== 원본 스냅샷 (진단 당시 상태 보존) ====================
    original_provider = models.CharField(
        max_length=10,
        choices=Provider.choices,
        help_text="원본 프로바이더 (진단 당시 스냅샷)",
    )
    original_instance_type = models.CharField(
        max_length=50,
        help_text="원본 인스턴스 타입 (진단 당시 스냅샷)",
    )
    original_monthly_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="원본 월 비용 (진단 당시 스냅샷)",
    )
    original_cpu_usage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="원본 CPU 사용률 (진단 당시 스냅샷)",
    )

    # ==================== 추천 결과 ====================
    expected_monthly_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="추천 서비스 적용 시 예상 월 비용",
    )
    savings_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="예상 절감액 (original - expected)",
    )
    savings_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="절감률 (%)",
    )

    # ==================== AI 추천 근거 ====================
    reason = models.TextField(
        help_text="AI가 생성한 추천 근거 및 설명",
    )
    confidence_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=80.00,
        help_text="추천 신뢰도 점수 (0~100)",
    )

    # ==================== 우선순위 ====================
    priority = models.IntegerField(
        default=1,
        help_text="추천 우선순위 (1이 가장 높음)",
    )

    class Meta:
        db_table = "recommendation_items"
        ordering = ["priority", "-savings_amount"]
        indexes = [
            # 추천 결과별 아이템 조회
            models.Index(fields=["recommendation"]),
            # 추천 유형별 필터링
            models.Index(fields=["recommendation_type"]),
        ]

    def __str__(self):
        recommended = self.recommended_service.instance_type if self.recommended_service else "N/A"
        return f"{self.original_instance_type} → {recommended} (${self.savings_amount} 절감)"

    def save(self, *args, **kwargs):
        """저장 시 절감액/절감률 자동 계산"""
        if self.original_monthly_cost and self.expected_monthly_cost:
            self.savings_amount = self.original_monthly_cost - self.expected_monthly_cost
            if self.original_monthly_cost > 0:
                self.savings_percentage = (self.savings_amount / self.original_monthly_cost) * 100
        super().save(*args, **kwargs)
