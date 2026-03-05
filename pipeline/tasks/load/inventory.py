import logging

from prefect import task

from apps.core.dto.inventory_dto import EC2InventoryDTO
from apps.inventories.models import UserInventory

logger = logging.getLogger(__name__)


@task
def load_inventory(user, dtos: list[EC2InventoryDTO]) -> list[UserInventory]:
    results = []
    for dto in dtos:
        inventory, created = UserInventory.objects.update_or_create(
            user=user,
            provider="AWS",
            resource_id=dto.resource_id,
            defaults={
                "instance_type": dto.instance_type,
                "region": dto.region,
                "region_normalized": dto.region_normalized,
                "vcpu": dto.vcpu,
                "memory_gb": dto.memory_gb,
                "current_monthly_cost": dto.current_monthly_cost,
                "currency": "USD",
                "cpu_usage_avg": dto.cpu_usage_avg,
                "is_active": True,
            },
        )

        action = "생성" if created else "갱신"
        logger.info("inventory %s: user=%s resource_id=%s", action, user.id, dto.resource_id)
        results.append(inventory)
    return results
