from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model

import pytest

from apps.inventories.models import UserInventory
from apps.recommendations.models import Recommendation, RecommendationItem
from apps.recommendations.services.audit_service import AuditService

User = get_user_model()

MOCK_AI_RESULT = {
    "diagnosis": "과스펙이 감지되었습니다",
    "recommendation_type": "SWITCH_PROVIDER",
    "recommended_provider": "GCP",
    "recommended_instance": "n1-standard-1",
    "reason": "월 $7.3 절감 가능합니다",
}


@pytest.fixture
def user(db):
    return User.objects.create_user(email="test@test.com", password="test1234")


@pytest.fixture
def make_inventory(user):
    def _factory(**kwargs):
        defaults = dict(
            user=user,
            provider="AWS",
            resource_id="i-1234567890",
            instance_type="t3.medium",
            region="ap-northeast-1",
            region_normalized="KR",
            vcpu=2,
            memory_gb=Decimal("4"),
            current_monthly_cost=Decimal("30"),
            cpu_usage_avg=None,
        )
        defaults.update(kwargs)
        return UserInventory.objects.create(**defaults)

    return _factory


@pytest.fixture
def mock_gemini():
    with patch(
        "apps.recommendations.services.audit_service.GeminiAdapter.generate_audit",
        return_value=MOCK_AI_RESULT,
    ) as m:
        yield m


# 기본 동작


@pytest.mark.django_db
def test_inventory_not_found(user):
    # 존재하지 않는 인벤토리 ID 조회 시 error 반환
    result = AuditService().audit(inventory_id=999, user=user)

    assert "error" in result


@pytest.mark.django_db
def test_no_comparable_provider_returns_error(make_inventory, aws_instance, mock_gemini):
    # 타 provider 인스턴스가 DB에 없을떄 error 반환하는지 검증

    inventory = make_inventory()

    result = AuditService().audit(inventory_id=inventory.id, user=inventory.user)

    assert "error" in result


# --- 비즈니스 로직 ---


@pytest.mark.django_db
def test_switch_provider_analysis_type(make_inventory, aws_instance, gcp_instance, mock_gemini):
    # cpu_usage_avg >= 30%  일떄 SWITCH_PROVIDER로 분기되는지 검증

    inventory = make_inventory(cpu_usage_avg=Decimal("50"))

    result = AuditService().audit(inventory_id=inventory.id, user=inventory.user)

    assert result["analysis_type"] == "SWITCH_PROVIDER"


@pytest.mark.django_db
def test_rightsizing_analysis_type(make_inventory, make_cloud_service, mock_gemini):
    # cpu_usage_avg >= 30%  일떄 RIGHTSIZING으로 분기되는지 검증

    make_cloud_service(
        provider="GCP",
        instance_type="n1-small",
        vcpu=1,
        memory_gb=Decimal("2"),
        price_per_hour=Decimal("0.02"),
    )
    inventory = make_inventory(cpu_usage_avg=Decimal("20"))

    result = AuditService().audit(inventory_id=inventory.id, user=inventory.user)

    assert result["analysis_type"] == "RIGHTSIZING"


@pytest.mark.django_db
def test_recommendation_saved_to_db(make_inventory, aws_instance, gcp_instance, mock_gemini):
    # audit 실행 후 Recommendation이 DB에 저장되는지 검증

    inventory = make_inventory()

    AuditService().audit(inventory_id=inventory.id, user=inventory.user)

    assert Recommendation.objects.filter(inventory_id=inventory.id).exists()


@pytest.mark.django_db
def test_recommendation_items_saved_to_db(make_inventory, aws_instance, gcp_instance, mock_gemini):
    # audit 실행 후 RecommendationItem이 DB에 저장되는지 검증

    inventory = make_inventory()

    AuditService().audit(inventory_id=inventory.id, user=inventory.user)

    recommendation = Recommendation.objects.get(inventory_id=inventory)
    assert RecommendationItem.objects.filter(recommendation=recommendation).exists()
