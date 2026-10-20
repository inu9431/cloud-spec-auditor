import pytest

from apps.core.choices import NormalizedRegion
from apps.core.utils.region_mapper import get_provider_regions, normalize_region

# --- normalize_region ---


def test_aws_region_mapper():
    # AWS 리전명이 정규화된 NormalizedRegion으로 변환되는지 검증
    assert normalize_region("ap-northeast-2") == NormalizedRegion.KR


def test_gcp_region_mapper():
    # GCP 리전명이 정규화된 NormalizedRegion으로 변환되는지 검증
    assert normalize_region("asia-northeast3") == NormalizedRegion.KR


def test_azure_region_mapper():
    # Azure 리전명이 정규화된 NormalizedRegion으로 변환되는지 검증
    assert normalize_region("koreacentral") == NormalizedRegion.KR


def test_unknown_region_mapper():
    # 매핑되지 않은 리전명 입력 시 ValueError가 발생하는지 검증
    with pytest.raises(ValueError):
        normalize_region("unknown-region-99")


# --- get_provider_regions ---


def test_get_provider_regions_kr():
    # KR 리전에 3사 원본 리전명이 모두 포함되는지 검증
    result = get_provider_regions(NormalizedRegion.KR)
    assert "ap-northeast-2" in result["AWS"]
    assert "asia-northeast3" in result["GCP"]
    assert "koreacentral" in result["AZURE"]


def test_get_provider_regions_returns_all_keys():
    # 반환값에 AWS/GCP/AZURE 키가 모두 포함되는지 검증
    result = get_provider_regions(NormalizedRegion.US_EAST)
    assert set(result.keys()) == {"AWS", "GCP", "AZURE"}
