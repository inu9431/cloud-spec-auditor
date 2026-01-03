from django.db import models
from django.conf import settings
from apps.core.models import BaseModel

class Recommendation(BaseModel):
    """
    AI가 생성한 전체 추천 결과
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    user_query = models.TextField()
    ai_answer = models.TextField()
"""
모델 생성후 주석 풀것
"""
#    services = models.ManyToManyField(
#        'costs.CloudServices',
#        through='RecommendationItem',
#        related_name= 'recommendations'
#    )

#    class Meta:
#        db_table = 'recommendations'

class RecommendationItem(models.Model):
    """
    추천 결과와 개별 클라우드 서비스 사이 매핑 테이블
    """
    recommendation = models.ForeignKey(Recommendation, on_delete=models.CASCADE)
#  service = models.ForeignKey('costs.CloudService', on_delete=models.CASCADE)
    reason = models.CharField(max_length=255)

    class Meta:
        db_table = 'recommendation_items'