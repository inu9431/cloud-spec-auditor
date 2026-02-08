from django.db import models


class Provider(models.TextChoices):
    """클라우드 서비스 제공자"""

    AWS = "AWS", "Amazon Web Services"
    GCP = "GCP", "Google Cloud Platform"
    AZURE = "AZURE", "Microsoft Azure"


class NormalizedRegion(models.TextChoices):
    """정규화된 리전 (3사 비교용)"""

    # 아시아
    KR = "KR", "South Korea"
    JP = "JP", "Japan"
    SG = "SG", "Singapore"
    HK = "HK", "Hong Kong"
    IN = "IN", "India"
    AU = "AU", "Australia"

    # 북미
    US_EAST = "US_EAST", "US East"
    US_WEST = "US_WEST", "US West"
    CA = "CA", "Canada"

    # # 유럽
    # EU_WEST = "EU_WEST", "Europe West"
    # EU_NORTH = "EU_NORTH", "Europe North"
    # UK = "UK", "United Kingdom"
    # DE = "DE", "Germany"
    # FR = "FR", "France"
    #
    # # 남미
    # BR = "BR", "Brazil"
