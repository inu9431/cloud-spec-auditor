from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    """커스텀 사용자 모델"""
    # 기본필드는 AbstractUser에서 상속

    # 추가 필드
    company_name = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)

    # AWS 연동 정보 (나중에 암호화)
    aws_access_key = models.CharField(max_length=200, blank=True, null=True)
    aws_secret_key = models.CharField(max_length=200, blank=True, null=True)
    aws_region = models.CharField(max_length=50, default='us-east-1')

    # 구독 정보
    is_premium = models.BooleanField(default=False)
    subscription_ends_at = models.DateField(null=True, blank=True)

    # 메타 정보
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'
        verbose_name = '사용자'
        verbose_name_plural = '사용자 목록'
    
    def __str__(self):
        return f"{self.username} ({self.email})"
    
    @property
    def has_aws_credentials(self):
        """AWS 연동 여부 확인"""
        return bool(self.aws_access_key and self.aws_secret_key)