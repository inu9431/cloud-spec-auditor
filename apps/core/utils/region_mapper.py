from apps.core.choices import NormalizedRegion

REGION_MAPPING: dict[str, NormalizedRegion] = {
    # ===== AWS =====
    # 아시아
    "ap-northeast-2": NormalizedRegion.KR,
    "ap-northeast-1": NormalizedRegion.JP,
    "ap-northeast-3": NormalizedRegion.JP,
    "ap-southeast-1": NormalizedRegion.SG,
    "ap-east-1": NormalizedRegion.HK,
    "ap-south-1": NormalizedRegion.IN,
    "ap-southeast-2": NormalizedRegion.AU,
    # 북미
    "us-east-1": NormalizedRegion.US_EAST,
    "us-east-2": NormalizedRegion.US_EAST,
    "us-west-1": NormalizedRegion.US_WEST,
    "us-west-2": NormalizedRegion.US_WEST,
    "ca-central-1": NormalizedRegion.CA,
    # # 유럽
    # "eu-west-1": NormalizedRegion.EU_WEST,
    # "eu-west-2": NormalizedRegion.UK,
    # "eu-west-3": NormalizedRegion.FR,
    # "eu-central-1": NormalizedRegion.DE,
    # "eu-north-1": NormalizedRegion.EU_NORTH,
    # # 남미
    # "sa-east-1": NormalizedRegion.BR,
    # ===== GCP =====
    # 아시아
    "asia-northeast3": NormalizedRegion.KR,
    "asia-northeast1": NormalizedRegion.JP,
    "asia-northeast2": NormalizedRegion.JP,
    "asia-southeast1": NormalizedRegion.SG,
    "asia-east2": NormalizedRegion.HK,
    "asia-south1": NormalizedRegion.IN,
    "australia-southeast1": NormalizedRegion.AU,
    # 북미
    "us-east1": NormalizedRegion.US_EAST,
    "us-east4": NormalizedRegion.US_EAST,
    "us-west1": NormalizedRegion.US_WEST,
    "us-west2": NormalizedRegion.US_WEST,
    "northamerica-northeast1": NormalizedRegion.CA,
    # # 유럽
    # "europe-west1": NormalizedRegion.EU_WEST,
    # "europe-west2": NormalizedRegion.UK,
    # "europe-west3": NormalizedRegion.DE,
    # "europe-west4": NormalizedRegion.EU_WEST,
    # "europe-west9": NormalizedRegion.FR,
    # "europe-north1": NormalizedRegion.EU_NORTH,
    # # 남미
    # "southamerica-east1": NormalizedRegion.BR,
    # ===== Azure =====
    # 아시아
    "koreacentral": NormalizedRegion.KR,
    "koreasouth": NormalizedRegion.KR,
    "japaneast": NormalizedRegion.JP,
    "japanwest": NormalizedRegion.JP,
    "southeastasia": NormalizedRegion.SG,
    "eastasia": NormalizedRegion.HK,
    "centralindia": NormalizedRegion.IN,
    "australiaeast": NormalizedRegion.AU,
    # 북미
    "eastus": NormalizedRegion.US_EAST,
    "eastus2": NormalizedRegion.US_EAST,
    "westus": NormalizedRegion.US_WEST,
    "westus2": NormalizedRegion.US_WEST,
    "westus3": NormalizedRegion.US_WEST,
    "canadacentral": NormalizedRegion.CA,
    # # 유럽
    # "westeurope": NormalizedRegion.EU_WEST,
    # "uksouth": NormalizedRegion.UK,
    # "ukwest": NormalizedRegion.UK,
    # "germanywestcentral": NormalizedRegion.DE,
    # "francecentral": NormalizedRegion.FR,
    # "northeurope": NormalizedRegion.EU_NORTH,
    # # 남미
    # "brazilsouth": NormalizedRegion.BR,
}


def normalize_region(provider_region: str) -> NormalizedRegion:
    """
    Provider별 리전명을 정규화된 리전으로 변환

    Args:
        provider_region: AWS/GCP/Azure 원본 리전명

    Returns:
        NormalizedRegion enum 값

    Raises:
        ValueError: 매핑되지 않은 리전
    """
    normalized = REGION_MAPPING.get(provider_region)
    if normalized is None:
        raise ValueError(f"Unknown region: {provider_region}")
    return normalized


def get_provider_regions(normalized: NormalizedRegion) -> dict[str, list[str]]:
    """
    정규화된 리전에 해당하는 각 provider의 원본 리전 목록 반환

    Args:
        normalized: 정규화된 리전

    Returns:
        {"AWS": ["ap-northeast-2"], "GCP": ["asia-northeast3"], ...}
    """
    result: dict[str, list[str]] = {"AWS": [], "GCP": [], "AZURE": []}

    for region, norm in REGION_MAPPING.items():
        if norm != normalized:
            continue

        if region.startswith(("ap-", "us-", "eu-", "ca-", "sa-")):
            result["AWS"].append(region)
        elif region.startswith(
            ("asia-", "australia-", "europe-", "northamerica-", "southamerica-")
        ):
            result["GCP"].append(region)
        else:
            result["AZURE"].append(region)

    return result
