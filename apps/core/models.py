from django.db import models

class BaseModel(models.Model):
    """
    모든 모델에 생성
    """
    craeted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True # 실제 DB 테이블 생성하지 않음

