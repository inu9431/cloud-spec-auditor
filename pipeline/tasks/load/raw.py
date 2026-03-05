import hashlib
import json
import logging

from prefect import task

from pipeline.raw.models import RawEC2Snapshot, RawPriceSnapshot
from apps.users.models import CloudCredential

logger = logging.getLogger(__name__)

@task
def save_raw_ec2(credential: CloudCredential, raw_data: dict) -> RawEC2Snapshot | None:
    payload = raw_data
    payload_hash = hashlib.sha256(
        json.dumps(payload, default=str, sort_keys=True).encode("utf-8")
    ).hexdigest()

    if RawEC2Snapshot.objects.filter(payload_hash=payload_hash).exists():
        logger.info("raw_ec2 중복 skip: user=%s hash=%s", credential.user_id, payload_hash[:8])
        return None

    snapshot = RawEC2Snapshot.objects.create(
        user = credential.user,
        credential_id=credential.id,
        payload=payload,
        fetched_at = payload["fetched_at"],
        payload_hash=payload_hash,
    )
    logger.info("raw_ec2 저장 : user=%s snapshot_id=%d", credential.user_id, snapshot.id)
    return snapshot

@task
def save_raw_price(provider: str, region: str, raw_data: list) -> RawPriceSnapshot | None:
    from django.utils import timezone
    payload = {"prices": raw_data, "fetched_at": str(timezone.now())}
    payload_hash = hashlib.sha256(
        json.dumps(payload, default=str, sort_keys=True).encode("utf-8")
    ).hexdigest()

    if RawPriceSnapshot.objects.filter(payload_hash=payload_hash).exists():
        logger.info("raw_price 중복 skip: provider=%s region=%s", provider, region)
        return None
    snapshot = RawPriceSnapshot.objects.create(
        provider = provider,
        region = region,
        payload = payload,
        payload_hash = payload_hash,
        fetched_at = payload["fetched_at"],
    )
    logger.info("raw_price 저장: provider=%s region=%s", provider, region)
    return snapshot