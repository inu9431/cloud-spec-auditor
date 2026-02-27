import json
from decimal import Decimal
from typing import List, Optional

from django.conf import settings

import boto3
import requests
from google.cloud import billing_v1
from google.oauth2 import service_account

from apps.core.dto.cloud_service_dto import CloudServiceDTO
from apps.core.utils.region_mapper import normalize_region
from apps.costs.choices import PricingModel, PricingSource

AZURE_PRICING_URL = "https://prices.azure.com/api/retail/prices"
GCP_COMPUTE_SERVICE = "services/6F81-5844-456A"

# GCP는 SKU가 인스턴스 단위가 아닌 vCPU/RAM 단위로 제공되므로
# 인스턴스 스펙과 SKU 패밀리 매핑을 별도로 관리
GCP_MACHINE_SPECS: dict[str, dict] = {
    "n1-standard-1": {"vcpu": 1, "memory_gb": Decimal("3.75")},
    "n1-standard-2": {"vcpu": 2, "memory_gb": Decimal("7.5")},
    "n1-standard-4": {"vcpu": 4, "memory_gb": Decimal("15")},
    "n1-standard-8": {"vcpu": 8, "memory_gb": Decimal("30")},
    "n1-standard-16": {"vcpu": 16, "memory_gb": Decimal("60")},
    "n2-standard-2": {"vcpu": 2, "memory_gb": Decimal("8")},
    "n2-standard-4": {"vcpu": 4, "memory_gb": Decimal("16")},
    "n2-standard-8": {"vcpu": 8, "memory_gb": Decimal("32")},
    "n2-standard-16": {"vcpu": 16, "memory_gb": Decimal("64")},
    "e2-standard-2": {"vcpu": 2, "memory_gb": Decimal("8")},
    "e2-standard-4": {"vcpu": 4, "memory_gb": Decimal("16")},
    "e2-standard-8": {"vcpu": 8, "memory_gb": Decimal("32")},
    "e2-standard-16": {"vcpu": 16, "memory_gb": Decimal("64")},
}

# GCP SKU description에서 머신 패밀리를 식별하는 매핑
GCP_SKU_FAMILY_MAP: dict[str, str] = {
    "N1 Predefined Instance Core": "n1",
    "N1 Predefined Instance Ram": "n1",
    "N2 Instance Core": "n2",
    "N2 Instance Ram": "n2",
    "E2 Instance Core": "e2",
    "E2 Instance Ram": "e2",
}


class CloudPriceAdapter:

    def fetch_azure_prices(self, region: str) -> List[CloudServiceDTO]:
        # requests Azure Retail Prices API 호출
        # 응답 JSON 파싱
        # CloudServiceDTO 리스트로 변환해서 반환
        results = []
        url = AZURE_PRICING_URL
        params = {
            "$filter": (
                f"armRegionName eq '{region}'"
                f" and serviceName eq 'Virtual Machines'"
                f" and priceType eq 'Consumption'"
            )
        }
        while url:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            for item in data.get("Items", []):
                dto = self._parse_azure_item(item)
                if dto:
                    results.append(dto)
            url = data.get("NextPageLink")
            params = {}  #  NextPageLink에 이미 파라미터 포함됨
        return results

    def _parse_azure_item(self, item: dict) -> CloudServiceDTO | None:
        # Window 제외
        if "Windows" in item.get("skuName", ""):
            return None

        # 시간당 가격만 처리
        if item.get("unitOfMeasure") != "1 Hour":
            return None

        instance_type = item.get("armSkuName", "")
        if not instance_type:
            return None

        region = item.get("armRegionName", "")

        try:
            region_normalized = normalize_region(region)
        except ValueError:
            return None

        price_type = item.get("type", "")
        if price_type == "Consumption":
            pricing_model = PricingModel.ON_DEMAND
        elif price_type == "Reservation":
            pricing_model = PricingModel.RESERVED
        elif price_type == "Spot":
            pricing_model = PricingModel.SPOT
        else:
            return None
        return CloudServiceDTO.from_azure(item, region_normalized, pricing_model)

    def fetch_aws_prices(self, region: str) -> List[CloudServiceDTO]:
        client = boto3.client("pricing", region_name="us-east-1")
        results = []

        paginator = client.get_paginator("get_products")
        pages = paginator.paginate(
            ServiceCode="AmazonEC2",
            Filters=[
                {"Type": "TERM_MATCH", "Field": "regionCode", "Value": region},
                {"Type": "TERM_MATCH", "Field": "operatingSystem", "Value": "Linux"},
                {"Type": "TERM_MATCH", "Field": "tenancy", "Value": "Shared"},
                {"Type": "TERM_MATCH", "Field": "capacitystatus", "Value": "Used"},
                {"Type": "TERM_MATCH", "Field": "preInstalledSw", "Value": "NA"},
            ],
        )

        for page in pages:
            for price_str in page["PriceList"]:
                price_data = json.loads(price_str)
                dto = self._parse_aws_item(price_data)
                if dto:
                    results.append(dto)
        return results

    def _parse_aws_item(self, data: dict) -> CloudServiceDTO | None:
        attributes = data.get("product", {}).get("attributes", {})

        instance_type = attributes.get("instanceType", "")
        if not instance_type:
            return None

        region = attributes.get("regionCode", "")
        try:
            region_normalized = normalize_region(region)
        except ValueError:
            return None

        # onDemand 가격 추출(중첩 구조)
        on_demand = data.get("terms", {}).get("OnDemand", {})
        if not on_demand:
            return None

        price_dimensions = list(on_demand.values())[0].get("priceDimensions", {})
        price_usd = list(price_dimensions.values())[0].get("pricePerUnit", {}).get("USD", "0")

        if Decimal(price_usd) == 0:
            return None

        return CloudServiceDTO.from_aws(attributes, region_normalized, price_usd)

    def fetch_gcp_prices(self, region: str) -> List[CloudServiceDTO]:
        credentials = service_account.Credentials.from_service_account_file(
            settings.GCP_CREDENTIALS_PATH,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
        client = billing_v1.CloudCatalogClient(credentials=credentials)

        cpu_prices: dict[str, Decimal] = {}  # {family: price_per_vcpu}
        ram_prices: dict[str, Decimal] = {}  # {family: price_per_gb}

        for sku in client.list_skus(parent=GCP_COMPUTE_SERVICE):
            if region not in list(sku.service_regions):
                continue
            if sku.category.usage_type != "OnDemand":
                continue

            desc = sku.description
            family = next((f for key, f in GCP_SKU_FAMILY_MAP.items() if key in desc), None)
            if family is None:
                continue

            unit_price = self._extract_gcp_unit_price(sku)
            if unit_price is None:
                continue

            if "Core" in desc:
                cpu_prices[family] = unit_price
            elif "Ram" in desc:
                ram_prices[family] = unit_price

        try:
            region_normalized = normalize_region(region)
        except ValueError:
            return []

        results = []
        for machine_type, specs in GCP_MACHINE_SPECS.items():
            family = machine_type.split("-")[0]
            cpu_p = cpu_prices.get(family)
            ram_p = ram_prices.get(family)
            if cpu_p is None or ram_p is None:
                continue

            price_per_hour = cpu_p * specs["vcpu"] + ram_p * specs["memory_gb"]
            dto = CloudServiceDTO.from_gcp(
                machine_type=machine_type,
                region=region,
                region_normalized=region_normalized,
                vcpu=specs["vcpu"],
                memory_gb=specs["memory_gb"],
                price_per_hour=price_per_hour,
            )
            results.append(dto)

        return results

    def _extract_gcp_unit_price(self, sku) -> Decimal | None:
        if not sku.pricing_info:
            return None
        tiers = sku.pricing_info[0].pricing_expression.tiered_rates
        if not tiers:
            return None
        units = tiers[0].unit_price.units
        nanos = tiers[0].unit_price.nanos
        return Decimal(str(units)) + Decimal(str(nanos)) / Decimal("1_000_000_000")
