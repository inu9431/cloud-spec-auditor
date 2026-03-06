import logging
from datetime import timedelta

from prefect import flow

from apps.core.choices import Provider

logger = logging.getLogger(__name__)


@flow(name="sync-user-inventory")
def sync_user_inventory(credential_id: int):
    """
    단일 유저 인벤토리 수집 + audit.
    POST /api/inventories/sync/ 에서 async_task로 호출된다.
    """
    from apps.users.models import CloudCredential

    try:
        credential = CloudCredential.objects.get(id=credential_id, is_active=True)
    except CloudCredential.DoesNotExist:
        logger.error("credential 없음: id=%d", credential_id)
        return

    if credential.provider == Provider.AWS:
        _aws_pipeline(credential)
    elif credential.provider == Provider.GCP:
        _gcp_pipeline(credential)
    elif credential.provider == Provider.AZURE:
        _azure_pipeline(credential)
    else:
        logger.warning("지원하지 않는 provider: %s", credential.provider)


def _aws_pipeline(credential):
    from pipeline.tasks.extract.aws import extract_ec2_instances
    from pipeline.tasks.load.inventory import load_inventory
    from pipeline.tasks.load.raw import save_raw_ec2
    from pipeline.tasks.transform.normalize import normalize_inventory
    from pipeline.tasks.transform.validate import validate_inventory

    try:
        raw_data = extract_ec2_instances(credential)
        snapshot = save_raw_ec2(credential, raw_data)
        if snapshot is None:
            logger.info("변경 없음, sync skip: user=%s", credential.user.email)
            return
        dtos = normalize_inventory(snapshot)
        dtos = validate_inventory(dtos)
        inventories = load_inventory(credential.user, dtos)
        logger.info(
            "inventory sync 완료: user=%s synced=%d", credential.user.email, len(inventories)
        )
        _run_audit_for_inventories(inventories)
    except Exception as e:
        logger.error("inventory sync 실패: user=%s error=%s", credential.user.email, str(e))


def _gcp_pipeline(credential):
    from pipeline.tasks.extract.gcp import extract_gcp_instances
    from pipeline.tasks.load.inventory import load_inventory
    from pipeline.tasks.transform.validate import validate_inventory

    try:
        raw_data = extract_gcp_instances(credential)
        dtos = [
            _raw_to_dto(inst, credential.gcp_project_id) for inst in raw_data.get("instances", [])
        ]
        dtos = [d for d in dtos if d is not None]
        dtos = validate_inventory(dtos)
        inventories = load_inventory(credential.user, dtos)
        logger.info(
            "GCP inventory sync 완료: user=%s synced=%d", credential.user.email, len(inventories)
        )
        _run_audit_for_inventories(inventories)
    except Exception as e:
        logger.error("GCP inventory sync 실패: user=%s error=%s", credential.user.email, str(e))


def _azure_pipeline(credential):
    from pipeline.tasks.extract.azure import extract_azure_instances
    from pipeline.tasks.load.inventory import load_inventory
    from pipeline.tasks.transform.validate import validate_inventory

    try:
        raw_data = extract_azure_instances(credential)
        dtos = [
            _raw_to_dto(inst, credential.azure_subscription_id)
            for inst in raw_data.get("instances", [])
        ]
        dtos = [d for d in dtos if d is not None]
        dtos = validate_inventory(dtos)
        inventories = load_inventory(credential.user, dtos)
        logger.info(
            "Azure inventory sync 완료: user=%s synced=%d", credential.user.email, len(inventories)
        )
        _run_audit_for_inventories(inventories)
    except Exception as e:
        logger.error("Azure inventory sync 실패: user=%s error=%s", credential.user.email, str(e))


def _raw_to_dto(inst: dict, project_or_subscription: str):
    from decimal import Decimal

    from apps.core.dto.inventory_dto import EC2InventoryDTO
    from apps.core.utils.region_mapper import normalize_region

    region = inst.get("region", "")
    try:
        region_normalized = normalize_region(region)
    except ValueError:
        logger.warning(
            "리전 정규화 실패 skip: instance_id=%s region=%s", inst.get("instance_id"), region
        )
        return None

    return EC2InventoryDTO(
        resource_id=str(inst.get("instance_id", "")),
        instance_type=inst.get("instance_type", ""),
        region=region,
        region_normalized=region_normalized,
        vcpu=inst.get("vcpu", 0),
        memory_gb=Decimal(str(inst.get("memory_gb", 0))),
        current_monthly_cost=Decimal("0"),
        cpu_usage_avg=None,
        cost_fetched_at=None,
    )


@flow(name="sync-all-inventories")
def sync_all_inventories():
    """
    24h 스케줄: 활성 AWS 자격증명을 가진 모든 유저의 인벤토리를 수집하고
    각 유저별로 audit을 자동 실행한다.
    """
    from apps.users.models import CloudCredential

    credentials = CloudCredential.objects.filter(
        is_active=True,
    ).select_related("user")

    for credential in credentials:
        try:
            from django_q.tasks import async_task

            async_task("pipeline.flows.inventory_flow.sync_user_inventory", credential.id)
        except Exception as e:
            logger.error(
                "태스크 큐 등록 실패: user=%s error=%s",
                credential.user.email,
                str(e),
            )


def _run_audit_for_inventories(inventories):
    """수집된 인벤토리에 대해 audit 자동 실행 (순차, Partial Failure 허용)"""
    from apps.recommendations.services.audit_service import AuditService

    for inv in inventories:
        try:
            AuditService().audit(inv.id, inv.user)
        except Exception as e:
            logger.warning("audit 실패 skip: inventory_id=%d error=%s", inv.id, e)


@flow(name="sync-cloud-prices")
def sync_cloud_prices():
    """
    주 1회 스케줄: 3사 가격 데이터 최신화.
    """
    from apps.core.adapters.cloud_price_adapter import CloudPriceAdapter
    from pipeline.tasks.load.prices import load_prices, validate_prices
    from pipeline.tasks.load.raw import save_raw_price

    adapter = CloudPriceAdapter()

    jobs = [
        ("AWS", "ap-northeast-2", adapter.fetch_aws_prices),
        ("AWS", "us-east-1", adapter.fetch_aws_prices),
        ("GCP", "asia-northeast3", adapter.fetch_gcp_prices),
        ("GCP", "us-east1", adapter.fetch_gcp_prices),
        ("AZURE", "koreacentral", adapter.fetch_azure_prices),
        ("AZURE", "eastus", adapter.fetch_azure_prices),
    ]
    for provider, region, fetch_fn in jobs:
        try:
            dtos = fetch_fn(region)
            save_raw_price(provider, region, dtos)
            dtos = validate_prices(dtos)
            load_prices(dtos)
        except Exception as e:
            logger.error(
                "price sync 실패: provider=%s region=%s error=%s", provider, region, str(e)
            )


if __name__ == "__main__":
    # prefect server start 후 실행하면 스케줄 등록됨
    # python pipeline/flows/inventory_flow.py
    sync_all_inventories.serve(
        name="sync-all-inventories-24h",
        interval=timedelta(hours=24),
    )
