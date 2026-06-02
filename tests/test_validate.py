import logging
from decimal import Decimal

import pytest

from apps.core.dto.inventory_dto import EC2InventoryDTO
from pipeline.tasks.transform.validate import validate_inventory


@pytest.fixture(autouse=True)
def patch_prefect_logger(monkeypatch):
    monkeypatch.setattr(
        "pipeline.tasks.transform.validate.get_run_logger",
        lambda **kwargs: logging.getLogger("test"),
    )


def make_dto(**kwargs):
    defaults = dict(
        resource_id="i-1234567890",
        instance_type="t3.medium",
        region="ap-northeast-2",
        region_normalized="KR",
        vcpu=2,
        memory_gb=Decimal("4"),
        current_monthly_cost=Decimal(30),
        cpu_usage_avg=None,
    )
    defaults.update(kwargs)
    return EC2InventoryDTO(**defaults)


def test_valid_dto_passed():
    # 정상 DTO가 필터링 없이 통과되는지 검증
    result = validate_inventory.fn([make_dto()])
    assert len(result) == 1


def test_missing_resource_id_filtered():
    # resource_id가 빈 값이면 필터링되는지 검증
    result = validate_inventory.fn([make_dto(resource_id="")])
    assert len(result) == 0


def test_missing_instance_type_filtered():
    # instance_type이 빈 값이면 필터링되는지 검증
    result = validate_inventory.fn([make_dto(instance_type="")])
    assert len(result) == 0


def test_zero_vcpu_filtered():
    # vcpu가 0 이하이면 필터링되는지 검증
    result = validate_inventory.fn([make_dto(vcpu=0)])
    assert len(result) == 0


def test_negative_cost_filtered():
    # 월 비용이 음수이면 필터링되는지 검증
    result = validate_inventory.fn([make_dto(current_monthly_cost=Decimal("-1"))])
    assert len(result) == 0


def test_unrealistic_cost_filtered():
    # 월 비용이 10000 초과이면 비현실적 값으로 필터링되는지 검증
    result = validate_inventory.fn([make_dto(current_monthly_cost=Decimal("99999"))])
    assert len(result) == 0


def test_cpu_usage_over_100_filtered():
    # cpu_usage_avg가 100 초과이면 필터링되는지 검증
    result = validate_inventory.fn([make_dto(cpu_usage_avg=Decimal("101"))])
    assert len(result) == 0


def test_mixed_valid_invalid():
    # 정상/비정상 DTO가 섞여있을 때 정상 DTO만 통과되는지 검증
    dtos = [make_dto(), make_dto(vcpu=0), make_dto(resource_id="")]
    result = validate_inventory.fn(dtos)
    assert len(result) == 1
