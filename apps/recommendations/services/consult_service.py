from decimal import Decimal

from apps.core.adapters.gemini_adapter import GeminiAdapter
from apps.core.exceptions.ai_exceptions import GeminiAPIError
from apps.costs.services.compare_service import InstanceCompareService


class ConsultService:

    def consult(self, description: str) -> dict:
        gemini = GeminiAdapter()

        # 1단계: 기획 → 스펙 + 리전 추정 (Gemini)
        try:
            spec = gemini.generate_consult_spec(description)
        except GeminiAPIError as e:
            return {"error": f"스펙 추정 실패: {str(e)}"}

        vcpu = spec.get("vcpu")
        memory_gb = spec.get("memory_gb")
        region = spec.get("region", "US_EAST")

        if not vcpu or not memory_gb:
            return {"error": "스펙 추정 결과가 올바르지 않습니다"}

        # 2단계: DB에서 3사 가격 비교 (Python)
        compare_result = InstanceCompareService().compare_by_spec(
            vcpu=vcpu,
            memory_gb=Decimal(str(memory_gb)),
            region_normalized=region,
        )
        if "error" in compare_result:
            return {
                "error": f"추정 스펙({vcpu}vcpu/{memory_gb}GB, {region})에 해당하는 인스턴스를 DB에서 찾을 수 없습니다. 가격 데이터를 먼저 sync해주세요.",
                "estimated_spec": spec,
            }

        # 3단계: 비교 결과 → 유저 설명 생성 (Gemini)
        try:
            explanation = gemini.generate_consult_explain(description, spec, compare_result)
        except GeminiAPIError:
            cheapest = compare_result["results"][0]
            explanation = {
                "summary": f"{vcpu}vcpu / {memory_gb}GB 기준으로 {region} 리전 3사 가격을 비교했습니다.",
                "recommended_provider": cheapest["provider"],
                "recommended_instance": cheapest["instance_type"],
                "reason": f"월 ${cheapest['price_per_month']:.2f} USD로 가장 저렴합니다. On-Demand 기준이며 Reserved/Spot 적용 시 추가 절감 가능합니다.",
                "architecture_tips": "트래픽 증가에 대비해 오토스케일링 설정을 권장합니다.",
            }

        return {
            "estimated_spec": spec,
            "compare_result": compare_result,
            "summary": explanation.get("summary"),
            "recommended_provider": explanation.get("recommended_provider"),
            "recommended_instance": explanation.get("recommended_instance"),
            "reason": explanation.get("reason"),
            "architecture_tips": explanation.get("architecture_tips"),
        }
