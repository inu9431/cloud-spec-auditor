from contextlib import nullcontext
from email.policy import default
from tokenize import blank_re

from django.conf import settings
from django.db import models

from apps.core.models import BaseModel
from apps.costs.models import CloudService


class Recommendation(BaseModel):
    """
    AI가 생성한 전체 추천 결과
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="recommendations"
    )
    total_current_cost = models.DecimalField(max_digits=10, decimal_places=2)
    total_optimized_cost = models.DecimalField(max_digits=10, decimal_places=2)
    total_savings = models.DecimalField(max_digits=10, decimal_places=2)
    savings_percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    diagnosis_summary = models.TextField()

    class Meta:
        db_table = "recommendations"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - ${self.total_savings} 절감 가능"

    def save(self, *args, **kwargs):
        if self.total_current_cost and self.total_savings:
            self.savings_percentage = self.total_savings / self.total_current_cost * 100
            super().save(*args, **kwargs)


class RecommendationItem(BaseModel):
    """
    추천 결과와 개별 클라우드 서비스 사이 매핑 테이블
    """

    recommendation = models.ForeignKey(
        Recommendation, on_delete=models.CASCADE, related_name="recommendation_items"
    )

    reason = models.CharField(max_length=255)

    # 추천 당시 스냅샷
    origin_provider = models.CharField(max_length=50, default="unknown")
    original_instance_type = models.CharField(max_length=50)
    original_monthly_cost = models.DecimalField(max_digits=10, decimal_places=2)
    original_cpu_usage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    recommended_service = models.ForeignKey(
        CloudService,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendation_items",
    )
    expected_monthly_cost = models.DecimalField(max_digits=10, decimal_places=2)
    savings_amount = models.DecimalField(max_digits=10, decimal_places=2)
    savings_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    reason = models.TextField()
    priority = models.IntegerField(default=1)

    class Meta:
        db_table = "recommendation_items"
        ordering = ["priority", "-savings_amount"]

    def __str__(self):
        return f"{self.original_instance_type} -> {self.recommended_service.instance_type if self.recommended_service else 'N/A'}"
