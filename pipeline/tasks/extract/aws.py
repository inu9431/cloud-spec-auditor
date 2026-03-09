import logging
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

from django.core.cache import cache
from django.utils import timezone

from prefect import task

from apps.core.adapters.aws_adapter import AWSAdapter
from apps.users.models import CloudCredential

logger = logging.getLogger(__name__)

CACHE_TTL_EC2 = 60 * 60
CACHE_TTL_OPTIMIZER = 60 * 60 * 12


def _build_adapter(credential: CloudCredential) -> AWSAdapter:
    return AWSAdapter(
        access_key=credential.aws_access_key_id,
        secret_key=credential.aws_secret_access_key,
        region=credential.aws_default_region or "ap-northeast-2",
    )


@task(retries=3, retry_delay_seconds=60)
def extract_ec2_instances(credential: CloudCredential) -> dict:
    key = f"ec2_instances:{credential.user_id}"
    cached = cache.get(key)
    if cached:
        return cached

    adapter = _build_adapter(credential)
    raw_instances = adapter.get_running_instances()

    instance_ids = [inst["instance_id"] for inst in raw_instances]
    bulk_costs = adapter.get_monthly_costs_bulk(instance_ids)
    cost_fetched_at = timezone.now()

    def _enrich(inst):
        instance_id = inst["instance_id"]
        instance_type = inst["instance_type"]
        optimizer_data = extract_rightsizing(credential, instance_id)
        specs = extract_instance_specs(credential, instance_type)
        return {
            **inst,
            "monthly_cost": bulk_costs.get(instance_id, 0.0),
            "cost_fetched_at": cost_fetched_at,
            "cpu_usage_avg": optimizer_data.get("cpu_usage_avg"),
            "vcpu": specs.get("vcpu", 0),
            "memory_gb": specs.get("memory_gb", Decimal("0")),
        }

    with ThreadPoolExecutor(max_workers=5) as executor:
        instances = list(executor.map(_enrich, raw_instances))

    result = {"instances": instances, "fetched_at": timezone.now()}
    cache.set(key, result, CACHE_TTL_EC2)
    return result


def extract_instance_specs(credential: CloudCredential, instance_type: str) -> dict:
    key = f"ec2_specs:{instance_type}"
    cached = cache.get(key)
    if cached:
        return cached

    try:
        adapter = _build_adapter(credential)
        response = adapter.ec2.describe_instance_types(InstanceTypes=[instance_type])
        info = response["InstanceTypes"][0]
        result = {
            "vcpu": info["VCpuInfo"]["DefaultVCpus"],
            "memory_gb": Decimal(str(info["MemoryInfo"]["SizeInMiB"])) / 1024,
        }
    except Exception as e:
        logger.warning("인스턴스 스펙 조회 실패: instance_type=%s error=%s", instance_type, str(e))
        result = {"vcpu": 0, "memory_gb": Decimal("0")}

    cache.set(key, result, 60 * 60 * 24 * 7)  # 7일 (스펙은 거의 안 바뀜)
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
