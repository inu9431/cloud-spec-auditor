import logging

from django.core.cache import cache
from django.utils import timezone

from prefect import task

from apps.core.adapters.azure_adapter import AzureAdapter
from apps.users.models import CloudCredential

logger = logging.getLogger(__name__)

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
    key = f"azure_instances:{credential.user_id}"
    cached = cache.get(key)
    if cached:
        logger.info("캐시 히트 - Azure 인스턴스")
        return cached

    adapter = _build_adapter(credential)
    raw_instances = adapter.get_running_instances()
    logger.info(f"Azure 인스턴스 {len(raw_instances)}개 수집 완료")

    result = {"instances": raw_instances, "fetched_at": timezone.now()}
    cache.set(key, result, CACHE_TTL_AZURE)
    return result
