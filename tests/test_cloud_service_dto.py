from decimal import Decimal

from apps.core.dto.cloud_service_dto import CloudServiceDTO
from apps.costs.choices import CpuArch

# --- from aws ---

def test_aws_arm_instance():
    # t4g(Graviton) 인스턴스가 ARM64로 판별되는지 검증
    dto = CloudServiceDTO.from_aws({"instanceType": "t4g.medium", "regionCode": "ap-northeast-2", "vcpu": "2", "memory": "4 GiB"}, "KR", "0.0416")
    assert dto.cpu_arch == CpuArch.ARM64

def test_aws_x86_instance():
    # t3 인스턴스가 x86_64로 판별되는지 검증
    dto = CloudServiceDTO.from_aws({"instanceType": "t3.medium", "regionCode": "ap-northeast-2", "vcpu": "2", "memory": "4 GiB"}, "KR", "0.0416")
    assert dto.cpu_arch == CpuArch.X86_64

def test_aws_t3_is_burstable():
    # t3 인스턴스가 버스터블로 판별되는지 검증
    dto = CloudServiceDTO.from_aws({"instanceType": "t3.medium", "regionCode": "ap-northeast-2", "vcpu": "2", "memory": "4 GiB"}, "KR", "0.0416")
    assert dto.is_burstable is True

def test_aws_m5_not_burstable():
    # m5 인스턴스가 버스터블이 아닌 것으로 판별되는지 검증
    dto = CloudServiceDTO.from_aws({"instanceType": "m5.large", "regionCode": "ap-northeast-2", "vcpu": "2", "memory": "8 GiB"}, "KR", "0.096")
    assert dto.is_burstable is False

def test_aws_memory_parsed():
    # "4 GiB" 형식의 메모리 문자열이 Decimal("4")로 파싱되는지 검증
    dto = CloudServiceDTO.from_aws({"instanceType": "t3.medium", "regionCode": "ap-northeast-2", "vcpu": "2", "memory": "4 GiB"}, "KR", "0.0416")
    assert dto.memory_gb == Decimal("4")


# --- from gcp ---

def test_gcp_t2a_is_arm():
    # GCP t2a(Ampere Altra) 인스턴스가 ARM64로 판별되는지 검증
    dto = CloudServiceDTO.from_gcp("t2a-standard-2", "asia-northeast3", "KR", 2, Decimal("8"), Decimal("0.07"))
    assert dto.cpu_arch == CpuArch.ARM64

def test_gcp_e2_micro_is_burstable():
    # GCP e2-micro가 버스터블 인스턴스로 판별되는지 검증
    dto = CloudServiceDTO.from_gcp("e2-micro", "asia-northeast3", "KR", 2, Decimal("1"), Decimal("0.01"))
    assert dto.is_burstable is True


# --- from azure ---

def test_azure_b_series_is_burstable():
    # Azure Standard_B 시리즈가 버스터블로 판별되는지 검증
    dto = CloudServiceDTO.from_azure({"armSkuName": "Standard_B2s", "armRegionName": "koreacentral", "retailPrice": 0.05, "currencyCode": "USD"}, "KR", "ON_DEMAND")
    assert dto.is_burstable is True

def test_azure_d_series_not_burstable():
    # Azure Standard_D 시리즈가 버스터블이 아닌 것으로 판별되는지 검증
    dto = CloudServiceDTO.from_azure({"armSkuName": "Standard_D2s_v3", "armRegionName": "koreacentral", "retailPrice": 0.1, "currencyCode": "USD"}, "KR", "ON_DEMAND")
    assert dto.is_burstable is False
