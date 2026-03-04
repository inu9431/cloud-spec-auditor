"""
3사(AWS/GCP/Azure) 가격 데이터 수집 및 적재 태스크.

CloudPriceAdapter로 각 클라우드의 On-Demand 가격을 가져와
CloudService 테이블에 upsert 한다.
"""

from django.utils import timezone

from apps.core.adapters.cloud_price_adapter import CloudPriceAdapter
from apps.core.dto.cloud_service_dto import CloudServiceDTO
from apps.core.utils.region_mapper import REGION_MAPPING
from apps.costs.models import CloudService


class PriceSyncService:
    def __init__(self):
        self.adapter = CloudPriceAdapter()

    def sync_aws_prices(self, region: str = None):
        if region:
            aws_regions = [region]
        else:
            aws_regions = [
                r for r in REGION_MAPPING if r.startswith(("ap-", "us-", "eu-", "ca-", "sa-"))
            ]
        for region in aws_regions:
            dtos = self.adapter.fetch_aws_prices(region)
            self._save_prices(dtos)

    def sync_gcp_prices(self, region: str = None):
        if region:
            gcp_regions = [region]
        else:
            gcp_regions = [
                r
                for r in REGION_MAPPING
                if r.startswith(
                    (
                        "asia-",
                        "australia-",
                        "europe-",
                        "northamerica-",
                        "southamerica-",
                        "us-east",
                        "us-west",
                    )
                )
                and not r.startswith(("us-east-", "us-west-"))  # AWS 리전 제외
            ]
        for region in gcp_regions:
            dtos = self.adapter.fetch_gcp_prices(region)
            self._save_prices(dtos)

    def sync_azure_prices(self, region: str = None):
        if region:
            azure_regions = [region]
        else:
            azure_regions = [
                r
                for r in REGION_MAPPING
                if not r.startswith(
                    (
                        "ap-",
                        "us-",
                        "eu-",
                        "ca-",
                        "sa-",  # AWS
                        "asia-",
                        "australia-",
                        "europe-",  # GCP
                        "northamerica-",
                        "southamerica-",
                    )
                )
            ]
        for region in azure_regions:
            dtos = self.adapter.fetch_azure_prices(region)
            self._save_prices(dtos)

    def _save_prices(self, dtos: list[CloudServiceDTO]):
        for dto in dtos:
            CloudService.objects.update_or_create(
                provider=dto.provider,
                instance_type=dto.instance_type,
                region=dto.region,
                pricing_model=dto.pricing_model,
                defaults={
                    "region_normalized": dto.region_normalized,
                    "vcpu": dto.vcpu,
                    "memory_gb": dto.memory_gb,
                    "price_per_hour": dto.price_per_hour,
                    "pricing_source": dto.pricing_source,
                    "currency": dto.currency,
                    "confidence_level": "HIGH",
                    "is_active": True,
                    "last_verified_at": timezone.now().date(),
                },
            )
