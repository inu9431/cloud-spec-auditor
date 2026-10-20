from dataclasses import dataclass, field
from decimal import Decimal

from apps.costs.choices import CpuArch, PricingModel, PricingSource

# AWS ARM 인스턴스 패밀리 접두사 (t4g, m6g, c6g, r6g, ...)
_AWS_ARM_PREFIXES = ("t4g", "m6g", "c6g", "r6g", "m7g", "c7g", "r7g", "hpc7g", "im4g", "is4g")
# AWS 버스터블 인스턴스 패밀리
_AWS_BURSTABLE_PREFIXES = ("t2", "t3", "t3a", "t4g")
# Azure ARM SKU 키워드 (이름에 'p' 시리즈 또는 _Arm 포함)
_AZURE_ARM_KEYWORDS = ("psv5", "pdsv5", "plsv5", "pls", "Dpsv5", "Dpdsv5", "Ep", "dpsv5", "dplsv5")
# Azure 버스터블 시리즈
_AZURE_BURSTABLE_PREFIXES = ("Standard_B",)
# GCP ARM 머신 패밀리 접두사
_GCP_ARM_PREFIXES = ("t2a",)
# GCP 버스터블 머신 유형
_GCP_BURSTABLE_TYPES = ("e2-micro", "e2-small", "e2-medium", "f1-micro", "g1-small")


def _aws_cpu_arch(instance_type: str) -> str:
    family = instance_type.split(".")[0]
    return CpuArch.ARM64 if any(family.startswith(p) for p in _AWS_ARM_PREFIXES) else CpuArch.X86_64


def _aws_is_burstable(instance_type: str) -> bool:
    family = instance_type.split(".")[0]
    return any(family.startswith(p) for p in _AWS_BURSTABLE_PREFIXES)


def _azure_cpu_arch(instance_type: str) -> str:
    lower = instance_type.lower()
    return CpuArch.ARM64 if any(k.lower() in lower for k in _AZURE_ARM_KEYWORDS) else CpuArch.X86_64


def _azure_is_burstable(instance_type: str) -> bool:
    return any(instance_type.startswith(p) for p in _AZURE_BURSTABLE_PREFIXES)


def _gcp_cpu_arch(machine_type: str) -> str:
    return (
        CpuArch.ARM64
        if any(machine_type.startswith(p) for p in _GCP_ARM_PREFIXES)
        else CpuArch.X86_64
    )


def _gcp_is_burstable(machine_type: str) -> bool:
    return machine_type in _GCP_BURSTABLE_TYPES


@dataclass
class CloudServiceDTO:
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
    cpu_arch: str = field(default=CpuArch.X86_64)
    is_burstable: bool = field(default=False)

    @classmethod
    def from_azure(
        cls, item: dict, region_normalized: str, pricing_model: str
    ) -> "CloudServiceDTO":
        instance_type = item.get("armSkuName", "")
        return cls(
            provider="AZURE",
            instance_type=instance_type,
            region=item.get("armRegionName", ""),
            region_normalized=region_normalized,
            vcpu=0,
            memory_gb=Decimal("0"),
            price_per_hour=Decimal(str(item.get("retailPrice", 0))),
            pricing_model=pricing_model,
            pricing_source=PricingSource.AZURE_API,
            currency=item.get("currencyCode", "USD"),
            cpu_arch=_azure_cpu_arch(instance_type),
            is_burstable=_azure_is_burstable(instance_type),
        )

    @classmethod
    def from_aws(
        cls,
        attributes: dict,
        region_normalized: str,
        price_usd: str,
        pricing_model: str = PricingModel.ON_DEMAND,
    ) -> "CloudServiceDTO":
        memory_str = attributes.get("memory", "0 GiB").replace(" GiB", "").replace(",", "")
        try:
            memory_gb = Decimal(memory_str)
        except Exception:
            memory_gb = Decimal("0")

        instance_type = attributes.get("instanceType", "")
        return cls(
            provider="AWS",
            instance_type=instance_type,
            region=attributes.get("regionCode", ""),
            region_normalized=region_normalized,
            vcpu=int(attributes.get("vcpu", 0)),
            memory_gb=memory_gb,
            price_per_hour=Decimal(price_usd),
            pricing_model=pricing_model,
            pricing_source=PricingSource.AWS_API,
            currency="USD",
            cpu_arch=_aws_cpu_arch(instance_type),
            is_burstable=_aws_is_burstable(instance_type),
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
        pricing_model: str = PricingModel.ON_DEMAND,
    ) -> "CloudServiceDTO":
        return cls(
            provider="GCP",
            instance_type=machine_type,
            region=region,
            region_normalized=region_normalized,
            vcpu=vcpu,
            memory_gb=memory_gb,
            price_per_hour=price_per_hour,
            pricing_model=pricing_model,
            pricing_source=PricingSource.GCP_API,
            currency="USD",
            cpu_arch=_gcp_cpu_arch(machine_type),
            is_burstable=_gcp_is_burstable(machine_type),
        )
