from django.db import models


class CloudService(models.Model):
    """크롤링 된 클라우드 서비스 상품 정보"""

    PROVIDER_CHOICES = [
        ("AWS", "Amazon Web Services"),
        ("GCP", "Google Cloud Platform"),
        ("AZURE", "Microsoft Azure"),
    ]

    # 기본 정보
    provider = models.CharField(max_length=10, choices=PROVIDER_CHOICES)
    instance_type = models.CharField(max_length=50)
    region = models.CharField(max_length=50, default="us-east-1")

    # 스펙
    vcpu = models.IntegerField()
    memory_gb = models.DecimalField(max_digits=6, decimal_places=2)
    storage_gb = models.IntegerField(null=True, blank=True)

    # 가격 정보
    price_per_hour = models.DecimalField(max_digits=10, decimal_places=4)
    price_per_month = models.DecimalField(max_digits=10, decimal_places=2)

    # 메타 정보
    crawled_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "cloud_services"
        indexes = [
            models.Index(fields=["provider", "instance_type"]),
            models.Index(fields=["vcpu", "memory_gb"]),
        ]
        ordering = ["provider", "price_per_month"]

    def __str__(self):
        return f"{self.provider} - {self.instance_type} (${self.price_per_month}/month)"
