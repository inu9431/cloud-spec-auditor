from prefect import get_run_logger, task

from apps.core.dto.inventory_dto import EC2InventoryDTO


@task
def validate_inventory(dtos: list[EC2InventoryDTO]) -> list[EC2InventoryDTO]:
    logger = get_run_logger()
    valid = []
    for dto in dtos:
        if not dto.resource_id:
            logger.warning("[VALIDATE_SKIP] reason=resource_id_missing")
            continue
        if not dto.instance_type:
            logger.warning(
                "[VALIDATE_SKIP] reason=instance_type_missing resource_id=%s",
                dto.resource_id,
            )
            continue
        if dto.vcpu <= 0:
            logger.warning(
                "[VALIDATE_SKIP] reason=vcpu_invalid resource_id=%s vcpu=%s",
                dto.resource_id,
                dto.vcpu,
            )
            continue
        if dto.memory_gb <= 0:
            logger.warning(
                "[VALIDATE_SKIP] reason=memory_invalid resource_id=%s memory_gb=%s",
                dto.resource_id,
                dto.memory_gb,
            )
            continue
        if dto.current_monthly_cost < 0:
            logger.warning(
                "[VALIDATE_SKIP] reason=negative_cost resource_id=%s cost=%s",
                dto.resource_id,
                dto.current_monthly_cost,
            )
            continue
        if dto.current_monthly_cost > 10000:
            logger.warning(
                "[VALIDATE_SKIP] reason=unrealistic_cost resource_id=%s cost=%s",
                dto.resource_id,
                dto.current_monthly_cost,
            )
            continue
        if dto.cpu_usage_avg is not None and dto.cpu_usage_avg > 100:
            logger.warning(
                "[VALIDATE_SKIP] reason=cpu_usage_invalid resource_id=%s cpu=%s",
                dto.resource_id,
                dto.cpu_usage_avg,
            )
            continue

        valid.append(dto)

    skipped = len(dtos) - len(valid)
    if skipped:
        logger.warning("[VALIDATE_SUMMARY] skipped=%d total=%d", skipped, len(dtos))
    logger.info("[VALIDATE_DONE] passed=%d total=%d", len(valid), len(dtos))
    return valid
