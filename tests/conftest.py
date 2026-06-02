from datetime import date
from decimal import Decimal

import pytest

from apps.costs.choices import PricingModel, PricingSource
from apps.costs.models import CloudService

@pytest.fixture
def make_cloud_service(db):
    def _factory(
        provider="AWS",
        instance_type = "t3.medium",
        region = "ap-northeast-2",
        region_normalized = "KR",
        vcpu=2,
        memory_gb=Decimal("4"),
        price_per_hour=Decimal("0.04"),
        pricing_model = PricingModel.ON_DEMAND,
        pricing_source=PricingSource.AWS_API,
        cpu_arch= "x86_64",
        is_burstable = False,
        is_active = True,
    ):
        return CloudService.objects.create(
                  provider=provider,
                  instance_type=instance_type,
                  region=region,
                  region_normalized=region_normalized,
                  vcpu=vcpu,
                  memory_gb=memory_gb,
                  price_per_hour=price_per_hour,
                  pricing_model=pricing_model,
                  pricing_source=pricing_source,
                  cpu_arch=cpu_arch,
                  is_burstable=is_burstable,
                  is_active=is_active,
                  currency="USD",
                  last_verified_at=date.today(),
              )

    return _factory

@pytest.fixture
def aws_instance(make_cloud_service):
    return make_cloud_service(
        provider="AWS",
        instance_type = "t3.medium",
        vcpu=2,
        memory_gb=Decimal("4"),
        price_per_hour=Decimal("0.04"),
        region_normalized = "KR",
    )

@pytest.fixture
def gcp_instance(make_cloud_service):
    return make_cloud_service(
        provider="GCP",
        instance_type="n1-standard-1",
        vcpu=2,
        memory_gb=Decimal("4"),
        price_per_hour=Decimal("0.05"),
        region_normalized="KR",
    )