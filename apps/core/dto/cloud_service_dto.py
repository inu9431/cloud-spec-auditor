from dataclasses import dataclass
from decimal import Decimal

from apps.costs.choices import PricingModel, PricingSource


@dataclass
class CloudServiceDTO:
    # Azure
    provider: str
    instance_type: str
    region: str
    region_normalized: str
    vcpu: int
    memory_gb: Decimal
    price_per_hour: Decimal
    pricing_model: str
    pricing_source: str
    currency: str

    @classmethod
    def from_azure(
        cls, item: dict, region_normalized: str, pricing_model: str
    ) -> "CloudServiceDTO":
        return cls(
            provider="AZURE",
            instance_type=item.get("armSkuName", ""),
            region=item.get("armRegionName", ""),
            region_normalized=region_normalized,
            vcpu=0,
            memory_gb=Decimal("0"),
            price_per_hour=Decimal(str(item.get("retailPrice", 0))),
            pricing_model=pricing_model,
            pricing_source=PricingSource.AZURE_API,
            currency=item.get("currencyCode", "USD"),
        )

    @classmethod
    def from_aws(
        cls, attributes: dict, region_normalized: str, price_usd: str
    ) -> "CloudServiceDTO":
        memory_str = attributes.get("memory", "0 GiB").replace(" GiB", "").replace(",", "")
        try:
            memory_gb = Decimal(memory_str)
        except Exception:
            memory_gb = Decimal("0")

        return cls(
            provider="AWS",
            instance_type=attributes.get("instanceType", ""),
            region=attributes.get("regionCode", ""),
            region_normalized=region_normalized,
            vcpu=int(attributes.get("vcpu", 0)),
            memory_gb=memory_gb,
            price_per_hour=Decimal(price_usd),
            pricing_model=PricingModel.ON_DEMAND,
            pricing_source=PricingSource.AWS_API,
            currency="USD",
        )

    @classmethod
    def from_gcp(
        cls,
        machine_type: str,
        region: str,
        region_normalized: str,
        vcpu: int,
        memory_gb: Decimal,
        price_per_hour: Decimal,
    ) -> "CloudServiceDTO":

        return cls(
            provider="GCP",
            instance_type=machine_type,
            region=region,
            region_normalized=region_normalized,
            vcpu=vcpu,
            memory_gb=memory_gb,
            price_per_hour=price_per_hour,
            pricing_model=PricingModel.ON_DEMAND,
            pricing_source=PricingSource.GCP_API,
            currency="USD",
        )
