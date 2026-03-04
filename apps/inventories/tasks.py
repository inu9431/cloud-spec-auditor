"""
django-q2 스케줄/비동기 태스크.

태스크 목록:
  - sync_user_inventory(credential_id)  : 단일 유저 수집 + audit (수동 sync 비동기 처리)
  - sync_all_inventories()              : 24h 스케줄 — 전체 유저 수집 + audit
  - sync_cloud_prices()                 : 주 1회 스케줄 — 3사 가격 최신화
"""

import logging

logger = logging.getLogger(__name__)


def sync_user_inventory(credential_id: int):
    """
    단일 유저 인벤토리 수집 + audit.
    POST /api/inventories/sync/ 에서 async_task로 호출된다.
    """
    from apps.inventories.services.cloudwatch_sync_service import InventorySyncService
    from apps.users.models import CloudCredential

    try:
        credential = CloudCredential.objects.get(id=credential_id, is_active=True)
    except CloudCredential.DoesNotExist:
        logger.error("credential 없음: id=%d", credential_id)
        return

    try:
        service = InventorySyncService(credential)
        inventories = service.sync()
        logger.info(
            "inventory sync 완료: user=%s synced=%d",
            credential.user.email,
            len(inventories),
        )
        _run_audit_for_inventories(inventories)
    except Exception as e:
        logger.error(
            "inventory sync 실패: user=%s error=%s",
            credential.user.email,
            str(e),
        )


def sync_all_inventories():
    """
    24h 스케줄: 활성 AWS 자격증명을 가진 모든 유저의 인벤토리를 수집하고
    각 유저별로 audit을 자동 실행한다.
    """
    from apps.core.choices import Provider
    from apps.users.models import CloudCredential

    credentials = CloudCredential.objects.filter(
        provider=Provider.AWS,
        is_active=True,
    ).select_related("user")

    for credential in credentials:
        # 유저별로 별도 태스크로 분리해 병렬 처리
        try:
            from django_q.tasks import async_task

            async_task("apps.inventories.tasks.sync_user_inventory", credential.id)
        except Exception as e:
            logger.error(
                "태스크 큐 등록 실패: user=%s error=%s",
                credential.user.email,
                str(e),
            )


def _run_audit_for_inventories(inventories):
    """수집된 인벤토리에 대해 audit 자동 실행"""
    from apps.recommendations.services.audit_service import AuditService

    for inventory in inventories:
        try:
            AuditService().audit(
                inventory_id=inventory.id,
                user=inventory.user,
            )
            logger.info("audit 완료: inventory_id=%d", inventory.id)
        except Exception as e:
            logger.error("audit 실패: inventory_id=%d error=%s", inventory.id, str(e))


def sync_cloud_prices():
    """
    주 1회 스케줄: 3사 가격 데이터 최신화.
    """
    from apps.costs.services.price_sync_service import PriceSyncService

    service = PriceSyncService()

    jobs = [
        ("AWS", "ap-northeast-2", service.sync_aws_prices),
        ("AWS", "us-east-1", service.sync_aws_prices),
        ("GCP", "asia-northeast3", service.sync_gcp_prices),
        ("GCP", "us-east1", service.sync_gcp_prices),
        ("AZURE", "koreacentral", service.sync_azure_prices),
        ("AZURE", "eastus", service.sync_azure_prices),
    ]

    for provider, region, fn in jobs:
        try:
            fn(region=region)
            logger.info("price sync 완료: provider=%s region=%s", provider, region)
        except Exception as e:
            logger.error(
                "price sync 실패: provider=%s region=%s error=%s",
                provider,
                region,
                str(e),
            )
