from contextlib import nullcontext
from email.policy import default
from tokenize import blank_re

from django.db import models
from django.conf import settings
from apps.core.models import BaseModel

class Recommendation(BaseModel):
    """
    AI가 생성한 전체 추천 결과
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
         on_delete=models.CASCADE,
        related_name='recommendations'
    )
    user_query = models.TextField()
    ai_answer = models.TextField()

    # 나중에 CloudService 모델 생기면 활성화
    # services = models.ManyToManyField(
    #     'costs.CloudService',
    #     through='RecommendationItem',
    #     related_name='recommendations'
    # )

    class Meta:
        db_table = 'recommendations'
        ordering = ['-created_at']

    def __str__(self):
        return f"Recommendation #{self.id} by {self.user}"

class RecommendationItem(BaseModel):
    """
    추천 결과와 개별 클라우드 서비스 사이 매핑 테이블
    """
    recommendation = models.ForeignKey(
        Recommendation,
        on_delete=models.CASCADE,
        related_name='recommendation_items'
    )

    # service = models.ForeignKey(
    #  'costs.CloudService',
    #  on_delete=models.CASCADE,
    # related_name = 'recommendation_items'
    #  )
    reason = models.CharField(max_length=255)

    # 추천 당시 스냅샷
    snapshot_provider = models.CharField(max_length=50,default="unknown")
    snapshot_region = models.CharField(max_length=50, default="unknown")
    snapshot_instance_type = models.CharField(max_length=100, default="unknown")
    snapshot_price_per_hour = models.FloatField(blank=True, null=True)

    confidence = models.FloatField(blank=True, null=True) # 추천 실뢰도
    risk_level =models.CharField(max_length=20, blank=True, null=True) # 안전/보수/공격적
    validated = models.FloatField(default=False) # 하드 룰 검증 통과여부

    class Meta:
        db_table = 'recommendation_items'
        ordering = ['id']
        # unique_together = ('recommendation', 'service')


    def __str__(self):
        # return f"{self.service} in recommendation {self.recommendation_id}"
        return f"Item {self.id} of Recommendation {self.recommendation_id}"