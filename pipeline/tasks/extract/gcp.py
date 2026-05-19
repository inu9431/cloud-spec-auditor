import logging

from django.core.cache import cache

from prefect import get_run_logger, task

from apps.core.adapters.gcp_adapter import GCPAdapter
from apps.users.models import CloudCredential

_logger = logging.getLogger(__name__)

CACHE_TTL_GCP = 60 * 60


def _build_adapter(credential: CloudCredential) -> GCPAdapter:
    return GCPAdapter(
        service_account_json=credential.gcp_service_account_json,
        project_id=credential.gcp_project_id,
    )


@task(retries=3, retry_delay_seconds=60)
def extract_gcp_instances(credential: CloudCredential) -> dict:
    from django.utils import timezone

    logger = get_run_logger()
    key = f"gcp_instances:{credential.user_id}"
    cached = cache.get(key)
    if cached:
        logger.info("[EXTRACT_EVENT] type=cache_hit provider=GCP user=%s", credential.user_id)
        return cached

    adapter = _build_adapter(credential)
    raw_instances = adapter.get_running_instances()
    result = {"instances": raw_instances, "fetched_at": timezone.now()}
    cache.set(key, result, CACHE_TTL_GCP)
    logger.info("[EXTRACT_EVENT] type=done provider=GCP user=%s count=%d", credential.user_id, len(raw_instances))
    return result
