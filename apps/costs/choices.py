from django.db import models


class PricingModel(models.TextChoices):
    """가격 모델"""

    ON_DEMAND = "ON_DEMAND", "On Demand"
    RESERVED = "RESERVED", "Reserved / Committed"
    SPOT = "SPOT", "Spot / Preemptible"


class PricingSource(models.TextChoices):
    """가격 데이터 출처"""

    AWS_API = "AWS_API", "AWS Price List API"
    GCP_API = "GCP_API", "GCP Cloud Billing API"
    AZURE_API = "AZURE_API", "Azure Retail Prices API"


class ConfidenceLevel(models.TextChoices):
    """가격 신뢰도"""

    HIGH = "HIGH", "High"
    MEDIUM = "MEDIUM", "Medium"
    LOW = "LOW", "Low"
