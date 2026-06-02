from decimal import Decimal

import pytest

from apps.costs.choices import PricingModel
from apps.costs.services.compare_service import InstanceCompareService


# --- 기본 동작 ---
@pytest.mark.django_db
def test_compare_by_spec_returns_results(aws_instance, gcp_instance):
    # 동일 스펙 인스턴스가 있을떄 results가 반환되는지 검증

    result = InstanceCompareService().compare_by_spec(vcpu=2, memory_gb=Decimal("4"))

    assert "results" in result
    assert len(result["results"]) == 2


@pytest.mark.django_db
def test_compare_by_spec_sorted_by_price(aws_instance, gcp_instance):
    # 결과가 price_per_hour 오름차순으로 정렬되는지 검증

    result = InstanceCompareService().compare_by_spec(vcpu=2, memory_gb=Decimal("4"))

    prices = [r["price_per_hour"] for r in result["results"]]
    assert prices == sorted(prices)


@pytest.mark.django_db
def test_compare_by_spec_missing_providers(aws_instance):
    # AWS만 있을떄 GCP/AZURE가 missing_providers에 포함되는지 검증

    result = InstanceCompareService().compare_by_spec(vcpu=2, memory_gb=Decimal("4"))

    assert "GCP" in result["missing_providers"]
    assert "AZURE" in result["missing_providers"]


@pytest.mark.django_db
def test_compare_by_spec_region_filter(make_cloud_service):
    # region_normalized 필터 적용시 해당 리전 인스턴스만 반환되는지 검증
    make_cloud_service(
        provider="AWS",
        instance_type="t3.medium",
        vcpu=2,
        memory_gb=Decimal("4"),
        region_normalized="KR",
    )
    make_cloud_service(
        provider="GCP",
        instance_type="n1-standard-1",
        vcpu=2,
        memory_gb=Decimal("4"),
        region_normalized="JP",
    )
    result = InstanceCompareService().compare_by_spec(
        vcpu=2, memory_gb=Decimal("4"), region_normalized="KR"
    )

    assert len(result["results"]) == 1
    assert result["results"][0]["provider"] == "AWS"


@pytest.mark.django_db
def test_compare_by_spec_no_match_returns_error():
    # 존재하지 않는 스펙 조회시 error 반환하는지 검증
    result = InstanceCompareService().compare_by_spec(vcpu=999, memory_gb=Decimal("999"))

    assert "error" in result


# --- 비즈니스 로직 ---


@pytest.mark.django_db
def tset_cheapest_summary(aws_instance, gcp_instance):
    # 가장 저렴한 provider/인스턴스가 summary.cheapest에 표시되는지 검증

    result = InstanceCompareService().compare_by_spec(vcpu=2, memory_gb=Decimal("4"))

    assert result["summary"]["cheapest"] == "AWSt3.medium"


@pytest.mark.django_db
def test_max_monthly_savings(aws_instance, gcp_instance):
    # 가장 비싼 인스턴스와 저렴한 인스턴스의 월 절감액 계산되는지 검증

    result = InstanceCompareService().compare_by_spec(vcpu=2, memory_gb=Decimal("4"))

    expected_savings = round((0.05 - 0.04) * 730, 2)
    assert result["summary"]["max_monthly_savings"] == expected_savings


@pytest.mark.django_db
def test_price_per_month_in_results(aws_instance):
    # 결과의 price_per_month가 price_per_hour * 730으로 계산되는지 검증

    result = InstanceCompareService().compare_by_spec(vcpu=2, memory_gb=Decimal("4"))

    assert result["results"][0]["price_per_month"] == 0.04 * 730


@pytest.mark.django_db
def test_reserved_pricing_excluded(make_cloud_service):
    # ON_DEMAND 외 pricing_model은 결과에서 제외되는지 검증

    make_cloud_service(
        provider="AWS",
        instance_type="t3.medium",
        vcpu=2,
        memory_gb=Decimal("4"),
        pricing_model=PricingModel.ON_DEMAND,
    )
    make_cloud_service(
        provider="AWS",
        instance_type="t3.medium",
        vcpu=2,
        memory_gb=Decimal("4"),
        pricing_model=PricingModel.RESERVED,
        region="us-east-1",
    )

    result = InstanceCompareService().compare_by_spec(vcpu=2, memory_gb=Decimal("4"))

    assert len(result["results"]) == 1


@pytest.mark.django_db
def test_inactive_instance_excluded(make_cloud_service):
    # is_active=False 인스턴스는 비교 결과에서 제외되는지 검증

    make_cloud_service(
        provider="AWS", instance_type="t3.medium", vcpu=2, memory_gb=Decimal("4"), is_active=False
    )

    result = InstanceCompareService().compare_by_spec(vcpu=2, memory_gb=Decimal("4"))

    assert "error" in result


@pytest.mark.django_db
def test_compare_by_instance_type(aws_instance, gcp_instance):
    # 인스턴스 타입 기준으로 스펙을 조회해 3사 비교가 되는지 검증

    result = InstanceCompareService().compare_by_instance_type("t3.medium")

    assert "results" in result
    assert len(result["results"]) == 2


@pytest.mark.django_db
def test_compare_by_instance_type_not_found():
    # 존재하지 않는 인스턴스 타입 조회 시 error 반환하는지 검증

    result = InstanceCompareService().compare_by_instance_type("nonexistent.type")

    assert "error" in result
