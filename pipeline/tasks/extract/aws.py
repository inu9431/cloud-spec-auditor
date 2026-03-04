import logging
from django.core.cache import cache
from django.utils import timezone

from apps.core.adapters.aws_adapter import AWSAdapter
from apps.users.models import CloudCredential

logger = logging.getLogger(__name__)

CACHE_TTL_EC2 = 60 * 60
CACHE_TTL_COST = 60 * 60 * 24
CACHE_TTL_OPTIMIZER = 60 * 60 * 12

def _build_adapter(credential: CloudCredential) -> AWSAdapter:
    return AWSAdapter(
        access_key = credential.aws_access_key_id,
        secret_key = credential.aws_secret_access_key,
        region=credential.aws_default_region or "ap-northeast-2",
    )

def extract_ec2_instances(credential: CloudCredential) -> dict:
    key = f"ec2_instances:{credential.user_id}"
    cached = cache.get(key)
    if cached:
        return cached

    adapter = _build_adapter(credential)
    instances = adapter.get_running_instances() # raw list
    result = {"instances": instances, "fetched_at": timezone.now()}
    cache.set(key, result, CACHE_TTL_EC2)
    return result

def extract_monthly_cost(credential: CloudCredential, instance_id: str) -> dict:
    key = f"ce_cost:{credential.user_id}:{instance_id}"
    cached = cache.get(key)
    if cached:
        return cached

    adapter = _build_adapter(credential)
    cost = adapter.get_monthly_cost(instance_id) # raw float
    result = {"instance_id": instance_id, "cost": cost, "fetched_at": timezone.now()}
    cache.set(key, result, CACHE_TTL_COST)
    return result


def extract_rightsizing(credential: CloudCredential, instance_id: str) -> dict:
    key = f"optimizer:{credential.user_id}:{instance_id}"
    cached = cache.get(key)
    if cached:
        return cached

    adapter = _build_adapter(credential)
    result = adapter.get_rightsizing_recommendations(instance_id)  # raw dict
    result["fetched_at"] = timezone.now()
    cache.set(key, result, CACHE_TTL_OPTIMIZER)
    return result