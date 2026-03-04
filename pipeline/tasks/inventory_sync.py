"""
AWS 인벤토리 자동 수집 태스크.

EC2 describe_instances → Cost Explorer (당월 비용) → Compute Optimizer (과스펙 판단)
세 API를 조합해 UserInventory를 update_or_create 한다.

캐시 전략 (FileBasedCache):
  - EC2 인스턴스 목록: 1h
  - Cost Explorer 비용: 24h
  - Compute Optimizer 추천: 12h
"""

from decimal import Decimal
from typing import List

from django.core.cache import cache

from apps.core.adapters.aws_adapter import AWSAdapter
from apps.core.utils.region_mapper import normalize_region
from apps.inventories.models import UserInventory
from apps.users.models import CloudCredential

# 인스턴스 타입별 스펙 (vcpu, memory_gb) 조회용 간이 매핑
# Compute Optimizer나 EC2 DescribeInstanceTypes 로 보완 가능
EC2_INSTANCE_SPECS: dict[str, dict] = {
    "t3.micro": {"vcpu": 2, "memory_gb": Decimal("1")},
    "t3.small": {"vcpu": 2, "memory_gb": Decimal("2")},
    "t3.medium": {"vcpu": 2, "memory_gb": Decimal("4")},
    "t3.large": {"vcpu": 2, "memory_gb": Decimal("8")},
    "t3.xlarge": {"vcpu": 4, "memory_gb": Decimal("16")},
    "t3.2xlarge": {"vcpu": 8, "memory_gb": Decimal("32")},
    "m5.large": {"vcpu": 2, "memory_gb": Decimal("8")},
    "m5.xlarge": {"vcpu": 4, "memory_gb": Decimal("16")},
    "m5.2xlarge": {"vcpu": 8, "memory_gb": Decimal("32")},
    "m5.4xlarge": {"vcpu": 16, "memory_gb": Decimal("64")},
    "c5.large": {"vcpu": 2, "memory_gb": Decimal("4")},
    "c5.xlarge": {"vcpu": 4, "memory_gb": Decimal("8")},
    "c5.2xlarge": {"vcpu": 8, "memory_gb": Decimal("16")},
    "c5.4xlarge": {"vcpu": 16, "memory_gb": Decimal("32")},
    "r5.large": {"vcpu": 2, "memory_gb": Decimal("16")},
    "r5.xlarge": {"vcpu": 4, "memory_gb": Decimal("32")},
    "r5.2xlarge": {"vcpu": 8, "memory_gb": Decimal("64")},
    "r5.4xlarge": {"vcpu": 16, "memory_gb": Decimal("128")},
}

CACHE_TTL_EC2 = 60 * 60  # 1h
CACHE_TTL_COST = 60 * 60 * 24  # 24h
CACHE_TTL_OPTIMIZER = 60 * 60 * 12  # 12h


class InventorySyncService:

    def __init__(self, credential: CloudCredential):
        self.credential = credential
        self.adapter = AWSAdapter(
            access_key=credential.aws_access_key_id,
            secret_key=credential.aws_secret_access_key,
            region=credential.aws_default_region or "ap-northeast-2",
        )

    def sync(self) -> List[UserInventory]:
        """
        EC2 + Cost Explorer + Compute Optimizer 수집 후 UserInventory upsert.
        생성/갱신된 UserInventory 목록을 반환한다.
        """
        instances = self._get_instances_cached()
        synced = []
        for inst in instances:
            instance_id = inst["instance_id"]
            instance_type = inst["instance_type"]
            region = inst["region"]

            monthly_cost = self._get_cost_cached(instance_id)
            optimizer = self._get_optimizer_cached(instance_id)
            specs = EC2_INSTANCE_SPECS.get(instance_type, {})

            try:
                region_normalized = normalize_region(region)
            except ValueError:
                continue

            inventory, _ = UserInventory.objects.update_or_create(
                user=self.credential.user,
                provider="AWS",
                resource_id=instance_id,
                defaults={
                    "instance_type": instance_type,
                    "region": region,
                    "region_normalized": region_normalized,
                    "vcpu": specs.get("vcpu", 0),
                    "memory_gb": specs.get("memory_gb", Decimal("0")),
                    "current_monthly_cost": Decimal(str(monthly_cost)),
                    "currency": "USD",
                    "cpu_usage_avg": (
                        Decimal(str(optimizer.get("cpu_usage_avg", 0)))
                        if optimizer.get("cpu_usage_avg")
                        else None
                    ),
                    "is_active": True,
                },
            )
            synced.append(inventory)
        return synced

    # ──────────────────────────────────────────────
    # 캐시 래퍼
    # ──────────────────────────────────────────────

    def _get_instances_cached(self) -> list:
        key = f"ec2_instances:{self.credential.user_id}"
        cached = cache.get(key)
        if cached is not None:
            return cached
        instances = self.adapter.get_running_instances()
        cache.set(key, instances, CACHE_TTL_EC2)
        return instances

    def _get_cost_cached(self, instance_id: str) -> float:
        key = f"ce_cost:{self.credential.user_id}:{instance_id}"
        cached = cache.get(key)
        if cached is not None:
            return cached
        cost = self.adapter.get_monthly_cost(instance_id)
        cache.set(key, cost, CACHE_TTL_COST)
        return cost

    def _get_optimizer_cached(self, instance_id: str) -> dict:
        key = f"optimizer:{self.credential.user_id}:{instance_id}"
        cached = cache.get(key)
        if cached is not None:
            return cached
        result = self.adapter.get_rightsizing_recommendations(instance_id)
        cache.set(key, result, CACHE_TTL_OPTIMIZER)
        return result
