import logging

from django.core.cache import cache

from prefect import task

from apps.core.adapters.gcp_adapter import GCPAdapter
from apps.users.models import CloudCredential

logger = logging.getLogger(__name__)

CACHE_TTL_GCP = 60 * 60


def _build_adapter(credential: CloudCredential) -> GCPAdapter:
    return GCPAdapter(
        service_account_json=credential.gcp_service_account_json,
        project_id=credential.gcp_project_id,
    )


@task(retries=3, retry_delay_seconds=60)
def extract_gcp_instances(credential: CloudCredential) -> dict:
    key = f"gcp_instances:{credential.user_id}"
    cached = cache.get(key)
    if cached:
        logger.info("캐시 히트 - GCP 인스턴스")
        return cached

    from django.utils import timezone

    adapter = _build_adapter(credential)
    raw_instances = adapter.get_running_instances()
    logger.info(f"GCP 인스턴스 {len(raw_instances)}개 수집 완료")
    result = {"instances": raw_instances, "fetched_at": timezone.now()}
    cache.set(key, result, CACHE_TTL_GCP)
    return result
