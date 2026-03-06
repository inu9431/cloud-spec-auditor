import logging

from prefect import task

from apps.core.dto.inventory_dto import EC2InventoryDTO
from apps.inventories.models import UserInventory

logger = logging.getLogger(__name__)


@task
def load_inventory(user, dtos: list[EC2InventoryDTO]) -> list[UserInventory]:
    if not dtos:
        return []

    existing = {
        inv.resource_id: inv
        for inv in UserInventory.objects.filter(
            user=user, provider="AWS", resource_id__in=[dto.resource_id for dto in dtos]
        )
    }

    to_create = []
    to_update = []
    update_fields = [
        "instance_type",
        "region",
        "region_normalized",
        "vcpu",
        "memory_gb",
        "current_monthly_cost",
        "cpu_usage_avg",
        "is_active",
        "cost_updated_at",
    ]

    for dto in dtos:
        if dto.resource_id in existing:
            inv = existing[dto.resource_id]
            inv.instance_type = dto.instance_type
            inv.region = dto.region
            inv.region_normalized = dto.region_normalized
            inv.vcpu = dto.vcpu
            inv.memory_gb = dto.memory_gb
            inv.current_monthly_cost = dto.current_monthly_cost
            inv.cpu_usage_avg = dto.cpu_usage_avg
            inv.is_active = True
            inv.cost_updated_at = dto.cost_fetched_at
            to_update.append(inv)
        else:
            to_create.append(
                UserInventory(
                    user=user,
                    provider="AWS",
                    resource_id=dto.resource_id,
                    instance_type=dto.instance_type,
                    region=dto.region,
                    region_normalized=dto.region_normalized,
                    vcpu=dto.vcpu,
                    memory_gb=dto.memory_gb,
                    current_monthly_cost=dto.current_monthly_cost,
                    currency="USD",
                    cpu_usage_avg=dto.cpu_usage_avg,
                    is_active=True,
                    cost_updated_at=dto.cost_fetched_at,
                )
            )

    if to_create:
        UserInventory.objects.bulk_create(to_create)
        logger.info("inventory 생성: user=%s count=%d", user.id, len(to_create))
    if to_update:
        UserInventory.objects.bulk_update(to_update, fields=update_fields)
        logger.info("inventory 갱신: user=%s count=%d", user.id, len(to_update))

    return list(existing.values()) + to_create
