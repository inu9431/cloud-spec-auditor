# core/dto/inventory_dto.py
from dataclasses import dataclass
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
