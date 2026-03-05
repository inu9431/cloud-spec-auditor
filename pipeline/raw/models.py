from django.contrib.auth import get_user_model
from django.db import models

from apps.core.models import BaseModel

User = get_user_model()


class RawSnapshotBase(BaseModel):
    payload = models.JSONField()
    fetched_at = models.DateTimeField()
    payload_hash = models.CharField(max_length=64, db_index=True, default="")

    class Meta:
        abstract = True


class RawEC2Snapshot(RawSnapshotBase):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="raw_ec2_snapshots")
    credential_id = models.IntegerField()

    class Meta:
        db_table = "raw_ec2_snapshots"
        indexes = [models.Index(fields=["user", "fetched_at"])]


class RawPriceSnapshot(RawSnapshotBase):
    provider = models.CharField(max_length=10)  # AWS | GCP | Azure
    region = models.CharField(max_length=50)

    class Meta:
        db_table = "raw_price_snapshots"
        indexes = [models.Index(fields=["provider", "region", "fetched_at"])]
