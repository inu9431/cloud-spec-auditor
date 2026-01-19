# core/dto/recommendation_dto.py
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class RecommendationItemDTO:
    """개별 추천 항목"""

    original_instance: str
    original_cost: float
    recommended_instance: str
    recommended_cost: float
    savings: float
    reason: str


@dataclass
class DiagnosisResultDTO:
    """AI 진단 최종 결과"""

    user_id: int
    total_current_cost: float
    total_optimized_cost: float
    total_savings: float
    diagnosis_summary: str
    items: List[RecommendationItemDTO]

    def to_dict(self):
        return {
            "total_savings": self.total_savings,
            "diagnosis_summary": self.diagnosis_summary,
            "items": [vars(item) for item in self.items],
        }
