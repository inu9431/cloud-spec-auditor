import logging

from django.core.cache import cache
from django.utils import timezone

from prefect import get_run_logger, task

from apps.core.adapters.azure_adapter import AzureAdapter
from apps.users.models import CloudCredential

_logger = logging.getLogger(__name__)

CACHE_TTL_AZURE = 60 * 60


def _build_adapter(credential: CloudCredential) -> AzureAdapter:
    return AzureAdapter(
        tenant_id=credential.azure_tenant_id,
        client_id=credential.azure_client_id,
        client_secret=credential.azure_client_secret,
        subscription_id=credential.azure_subscription_id,
    )


@task(retries=3, retry_delay_seconds=60)
def extract_azure_instances(credential: CloudCredential) -> dict:
    logger = get_run_logger()
    key = f"azure_instances:{credential.user_id}"
    cached = cache.get(key)
    if cached:
        logger.info("[EXTRACT_EVENT] type=cache_hit provider=AZURE user=%s", credential.user_id)
        return cached

    adapter = _build_adapter(credential)
    raw_instances = adapter.get_running_instances()
    result = {"instances": raw_instances, "fetched_at": timezone.now()}
    cache.set(key, result, CACHE_TTL_AZURE)
    logger.info("[EXTRACT_EVENT] type=done provider=AZURE user=%s count=%d", credential.user_id, len(raw_instances))
    return result
