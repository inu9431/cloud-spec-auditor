import logging
from decimal import Decimal

from prefect import task

from apps.core.dto.inventory_dto import EC2InventoryDTO
from apps.core.utils.region_mapper import normalize_region
from pipeline.raw.models import RawEC2Snapshot

logger = logging.getLogger(__name__)


@task
def normalize_inventory(snapshot: RawEC2Snapshot) -> list[EC2InventoryDTO]:
    instances = snapshot.payload.get("instances", [])
    dtos = []

    for inst in instances:
        instance_type = inst.get("instance_type", "")
        region = inst.get("region", "")

        try:
            region_normalized = normalize_region(region)
        except ValueError:
            logger.warning("리전 정규화 실패 skip: instance_id=%s region=%s", inst.get("instance_id"), region)
            continue

        dtos.append(EC2InventoryDTO(
            resource_id=inst.get("instance_id", ""),
            instance_type=instance_type,
            region=region,
            region_normalized=region_normalized,
            vcpu=inst.get("vcpu", 0),
            memory_gb=Decimal(str(inst.get("memory_gb", 0))),
            current_monthly_cost=Decimal(str(inst.get("monthly_cost", 0))),
            cpu_usage_avg=(
                Decimal(str(inst["cpu_usage_avg"]))
                if inst.get("cpu_usage_avg") is not None
                else None
            ),
        ))

    return dtos

