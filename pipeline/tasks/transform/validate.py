from prefect import get_run_logger, task

from apps.core.dto.inventory_dto import EC2InventoryDTO


@task
def validate_inventory(dtos: list[EC2InventoryDTO]) -> list[EC2InventoryDTO]:
    logger = get_run_logger()
    valid = []
    for dto in dtos:
        if not dto.resource_id:
            logger.warning("validate skip: resource_id 없음")
            continue
        if not dto.instance_type:
            logger.warning("validate skip: instance_type 없음 resource_id=%s", dto.resource_id)
            continue
        if dto.vcpu <= 0:
            logger.warning(
                "validate skip: vcpu 비정상 resource_id=%s vcpu=%s", dto.resource_id, dto.vcpu
            )
            continue
        if dto.memory_gb <= 0:
            logger.warning(
                "validate skip: memory_gb 비정상 resource_id=%s memory_gb=%s",
                dto.resource_id,
                dto.memory_gb,
            )
            continue
        if dto.current_monthly_cost <= 0:
            logger.warning(
                "비정상 가격 skip: resource_id=%s cost=%s",
                dto.resource_id,
                dto.current_monthly_cost,
            )
            continue
        if dto.current_monthly_cost > 10000:
            logger.warning(
                "비현실적 가격 skip: resource_id=%s cost=%s",
                dto.resource_id,
                dto.current_monthly_cost,
            )
            continue
        if dto.cpu_usage_avg is not None and dto.cpu_usage_avg > 100:
            logger.warning(
                "cpu_usage_avg 비정상 skip: resource_id=%s cpu=%s",
                dto.resource_id,
                dto.cpu_usage_avg,
            )
            continue

        valid.append(dto)
    return valid
