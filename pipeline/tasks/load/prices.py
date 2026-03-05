from decimal import Decimal

from django.utils import timezone

from prefect import get_run_logger, task

from apps.core.dto.cloud_service_dto import CloudServiceDTO
from apps.costs.models import CloudService


@task
def validate_prices(dtos: list[CloudServiceDTO]) -> list[CloudServiceDTO]:
    logger = get_run_logger()
    valid = []
    for dto in dtos:
        if dto.price_per_hour <= 0:
            logger.warning("가격 0 이하 skip: %s %s", dto.provider, dto.instance_type)
            continue
        if dto.price_per_hour > 100:
            logger.warning(
                "비현실적 가격 skip: %s %s price=%s",
                dto.provider,
                dto.instance_type,
                dto.price_per_hour,
            )
            continue
        valid.append(dto)
    return valid


@task
def load_prices(dtos: list[CloudServiceDTO]) -> int:
    logger = get_run_logger()
    count = 0
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
        count += 1
    logger.info("price 적재 완료: %d건", count)
    return count
