# core/dto/inventory_dto.py
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional


@dataclass
class CSVInventoryDTO:
    """CSV 파싱 결과"""

    resource_id: str
    instance_type: str
    provider: str
    vcpu: int
    memory_gb: float
    monthly_cost: float
    region: Optional[str] = "us-east-1"


@dataclass
class EC2InventoryDTO:
    """파이프 라인 normalize 결과 - UserInventory 적재 전 중간 표현"""

    resource_id: str
    instance_type: str
    region: str
    region_normalized: str
    vcpu: int
    memory_gb: Decimal
    current_monthly_cost: Decimal
    cpu_usage_avg: Optional[Decimal] = None
    cost_fetched_at: datetime | None = None
