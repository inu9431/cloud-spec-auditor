import hashlib
import json
import logging

from prefect import task

from apps.users.models import CloudCredential
from pipeline.raw.models import RawAzureSnapshot, RawEC2Snapshot, RawGCPSnapshot, RawPriceSnapshot

logger = logging.getLogger(__name__)


@task
def save_raw_ec2(credential: CloudCredential, raw_data: dict) -> RawEC2Snapshot | None:
    payload = json.loads(json.dumps(raw_data, default=str))
    payload_hash = hashlib.sha256(
        json.dumps(payload, default=str, sort_keys=True).encode("utf-8")
    ).hexdigest()

    if RawEC2Snapshot.objects.filter(payload_hash=payload_hash).exists():
        logger.info("raw_ec2 중복 skip: user=%s hash=%s", credential.user_id, payload_hash[:8])
        return None

    snapshot = RawEC2Snapshot.objects.create(
        user=credential.user,
        credential_id=credential.id,
        payload=payload,
        fetched_at=payload["fetched_at"],
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
        provider=provider,
        region=region,
        payload=payload,
        payload_hash=payload_hash,
        fetched_at=payload["fetched_at"],
    )
    logger.info("raw_price 저장: provider=%s region=%s", provider, region)
    return snapshot


@task
def save_raw_gcp(credential: CloudCredential, raw_data: dict) -> RawGCPSnapshot | None:
    payload = raw_data
    payload_hash = hashlib.sha256(
        json.dumps(payload, default=str, sort_keys=True).encode("utf-8")
    ).hexdigest()

    if RawGCPSnapshot.objects.filter(payload_hash=payload_hash).exists():
        logger.info("raw_gcp 중복 skip: user=%s hash=%s", credential.user_id, payload_hash[:8])
        return None

    snapshot = RawGCPSnapshot.objects.create(
        user=credential.user,
        credential_id=credential.id,
        project_id=credential.gcp_project_id,
        payload=payload,
        fetched_at=payload["fetched_at"],
        payload_hash=payload_hash,
    )
    logger.info("raw_gcp 저장: user=%s snapshot_id=%d", credential.user_id, snapshot.id)
    return snapshot


@task
def save_raw_azure(credential: CloudCredential, raw_data: dict) -> RawAzureSnapshot | None:
    payload = raw_data
    payload_hash = hashlib.sha256(
        json.dumps(payload, default=str, sort_keys=True).encode("utf-8")
    ).hexdigest()

    if RawAzureSnapshot.objects.filter(payload_hash=payload_hash).exists():
        logger.info("raw_azure 중복 skip: user=%s hash=%s", credential.user_id, payload_hash[:8])
        return None

    snapshot = RawAzureSnapshot.objects.create(
        user=credential.user,
        credential_id=credential.id,
        subscription_id=credential.azure_subscription_id,
        payload=payload,
        fetched_at=payload["fetched_at"],
        payload_hash=payload_hash,
    )
    logger.info("raw_azure 저장: user=%s snapshot_id=%d", credential.user_id, snapshot.id)
    return snapshot
