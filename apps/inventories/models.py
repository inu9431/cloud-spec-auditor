from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import BaseModel
User = get_user_model()

class UserInventory(BaseModel):
    """사용자가 현재 사용중인 클라우드 리소스"""
    
    PROVIDER_CHOICES = [
        ('AWS', 'Amazon Web Services'),
        ('GCP', 'Google Cloud Platform'),
        ('AZURE', 'Microsoft Azure'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='inventories'
    )

    # 리소스 기본 정보
    provider = models.CharField(max_length=10, choices=PROVIDER_CHOICES)
    resource_id = models.CharField(max_length=100)
    instance_type = models.CharField(max_length=50)
    region = models.CharField(max_length=50, default='us-east-1')

    # 스펙 정보
    vcpt = models.IntegerField()
    memory_gb = models.DecimalField(max_digits=6, decimal_places=2)
    storage_gb = models.IntegerField(null=True, blank=True)

    # 실제 사용률
    cpu_usage_avg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="평균 CPU 사용률 (%)"
    )
    memory_usage_avg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="평균 메모리 사용률 (%)"
    )

    current_monthly_cost = models.DecimalField(max_digits=10, decimal_places=2)

    # 메타 정보
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'user_inventories'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['provider', 'instance_type']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.provider} {self.instance_type}"

    @property
    def is_over_provisioned(self):
        """과다 스펙 여부(CPU 30% 미만)"""
        if self.cpu_usage_avg:
            return self.cpu_usage_avg < 30
        return None