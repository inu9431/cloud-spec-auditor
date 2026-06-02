from decimal import Decimal

import pytest


@pytest.mark.django_db
def test_price_per_month(make_cloud_service):
    # price_per_hour * 730으로 월 비용이 올바르게 계산되는지 검증
    service = make_cloud_service(price_per_hour=Decimal("0.1"))
    assert service.price_per_month == Decimal("0.1") * 730


@pytest.mark.django_db
def test_price_per_month_zero(make_cloud_service):
    # price_per_hour가 0일 때 월 비용도 0인지 검증
    service = make_cloud_service(price_per_hour=Decimal("0"))
    assert service.price_per_month == Decimal("0")


@pytest.mark.django_db
def test_str_representation(make_cloud_service):
    # __str__ 반환값에 provider와 instance_type이 포함되는지 검증
    service = make_cloud_service(provider="AWS", instance_type="t3.medium")
    assert "AWS" in str(service)
    assert "t3.medium" in str(service)
