import json
from decimal import Decimal

from apps.core.adapters.gemini_adapter import GeminiAdapter
from apps.core.exceptions.ai_exceptions import GeminiAPIError
from apps.costs.services.compare_service import InstanceCompareService
from apps.inventories.models import UserInventory
from apps.users.models import CloudCredential


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
        spec_for_gemini = {k: v for k, v in spec.items() if k != "storage_gb"}
        try:
            explanation = gemini.generate_consult_explain(
                description, spec_for_gemini, compare_result
            )
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

    def get_user_state(self, user) -> str:
        has_credential = CloudCredential.objects.filter(user=user, is_active=True).exists()
        if not has_credential:
            return "NOT_REGISTERED"
        has_inventory = UserInventory.objects.filter(user=user, is_active=True).exists()
        if not has_inventory:
            return "REGISTERED_NO_DATA"

        return "REGISTERED_WITH_DATA"

    def consult_chat(self, user_message: str, history: list, user) -> dict:
        gemini = GeminiAdapter()
        user_state = self.get_user_state(user)
        system_context = self._build_system_context(user_message, history, user_state, user)

        # 가격 데이터 없을 때 Gemini 호출 없이 고정 메시지 반환
        if system_context is None:
            return {
                "reply": "죄송합니다. 해당 스펙과 일치하는 가격 데이터를 찾지 못했습니다.\n서비스 규모나 원하시는 지역을 조금 더 구체적으로 말씀해 주시거나, 잠시 후 다시 시도해 주세요.",
                "user_state": user_state,
                "show_register_cta": user_state == "NOT_REGISTERED",
            }

        try:
            parsed = gemini.generate_consult_chat(user_message, history, system_context)
        except GeminiAPIError as e:
            return {"error": str(e)}

        parts = [
            parsed.get("spec_summary"),
            parsed.get("price_comparison"),
            parsed.get("architecture_tips"),
            parsed.get("cta"),
        ]
        reply = "\n\n".join(p for p in parts if p)

        return {
            "reply": reply,
            "user_state": user_state,
            "show_register_cta": user_state == "NOT_REGISTERED",
        }

    def _build_system_context(self, user_message: str, history: list, user_state: str, user) -> str:
        base = """당신은 클라우드 비용 최적화 전문가입니다.
타겟은 클라우드를 처음 접하는 개발자/메이커입니다. 기술 용어 대신 결과 중심 언어로 설명하세요.

[언어 규칙]
- vCPU는 "두뇌 개수", 메모리는 "작업 공간"으로 표현하되, 반드시 "동시에 N명이 써도 버벅임 없는 수준"처럼 체감되는 결과로 연결하세요.
- 인스턴스 타입명(예: t4g.small)은 반드시 "소규모 서버(t4g.small)"처럼 앞에 역할 설명을 붙이세요. 클라우드사 이름은 별도로 앞에 붙이므로 타입명 설명에 중복해서 넣지 마세요.
- 가격은 달러와 한화를 함께 표기하세요. 예: "$15.18 (약 2만 2천원)". 환율은 1달러 = 1,450원 기준.
- price_comparison에 반드시 장기 약정 할인(약 40% 절감) 가능성을 언급하세요.
- Reserved Instance는 "장기 약정 할인 (약 40% 절감)", Spot Instance는 "남는 자원 활용"으로 표현하세요.
- CTA에서 "AWS 키"라는 표현 대신 "AWS 계정을 연결하면"으로 표현하세요.
- 스토리지, 네트워크, DB는 절대 언급하지 마세요.
- EC2, Compute Engine, Azure VM 등 인스턴스 비교만 다루세요.

반드시 아래 JSON 형식으로만 응답하세요. 마크다운, 이모지, 설명 텍스트 없이 JSON만 출력하세요:
{{
  "spec_summary": "스펙을 체감 결과로 설명 1-2문장. 이미 설명했거나 해당 없으면 null",
  "price_comparison": "가격 비교 및 추천 이유 2-3문장. 달러+한화 병기 (필수)",
  "architecture_tips": "유저 서비스에 맞는 아키텍처 팁 1문장 (오토스케일링, CDN 등). 해당 없으면 null",
  "cta": "AWS 계정 연결 안내 1문장. NOT_REGISTERED 상태가 아니면 null"
}}"""

        if user_state == "REGISTERED_WITH_DATA":
            inventories = UserInventory.objects.filter(user=user, is_active=True)[:5]
            inventory_summary = [
                {
                    "provider": inv.provider,
                    "instance_type": inv.instance_type,
                    "region_normalized": inv.region_normalized,
                    "vcpu": inv.vcpu,
                    "memory_gb": float(inv.memory_gb),
                    "current_monthly_cost": float(inv.current_monthly_cost),
                    "cpu_usage_avg": float(inv.cpu_usage_avg) if inv.cpu_usage_avg else None,
                }
                for inv in inventories
            ]
            return f"""{base}

[유저 상태]
AWS 실계정 연동 완료. 아래 실제 인프라 데이터를 기반으로 분석하세요.

[현재 사용 중인 인프라]
{json.dumps(inventory_summary, ensure_ascii=False, indent=2)}

과스펙 인스턴스가 있으면 구체적인 절감 방안을 제시하세요."""

        elif user_state == "REGISTERED_NO_DATA":
            return f"""{base}

[유저 상태]
AWS 키 등록 완료, 인프라 데이터 수집 중 (14일 소요).
스펙 기반 3사 가격 비교를 제공하고, 14일 후 실계정 정밀 분석이 가능함을 안내하세요."""

        else:  # NOT_REGISTERED
            # 첫 번째 메시지에만 스펙 추정 + 가격 비교 (이후 메시지는 history로 맥락 유지)
            compare_section = ""
            if not history:
                try:
                    spec = GeminiAdapter().generate_consult_spec(user_message)
                    vcpu = spec.get("vcpu")
                    memory_gb = spec.get("memory_gb")
                    region = spec.get("region", "US_EAST")
                    if vcpu and memory_gb:
                        compare_result = InstanceCompareService().compare_by_spec(
                            vcpu=vcpu,
                            memory_gb=Decimal(str(memory_gb)),
                            region_normalized=region,
                        )
                        if "error" not in compare_result:
                            spec_for_context = {k: v for k, v in spec.items() if k != "storage_gb"}
                            compare_section = f"""
[추정 스펙]
{json.dumps(spec_for_context, ensure_ascii=False)}

[3사 가격 비교 (DB 실제 데이터)]
{json.dumps(compare_result, ensure_ascii=False, indent=2)}

위 데이터 기반으로 설명하세요. 숫자는 절대 변경하지 마세요.
제공된 가격 데이터에 없는 항목의 비용은 수치를 만들지 말고 '별도 확인 필요'라고 안내하세요."""
                except Exception:
                    pass  # 스펙 추정 실패 시 일반 채팅으로 fallback

            # 첫 메시지인데 가격 데이터 없으면 None 반환 → Gemini 호출 스킵
            if not compare_section and not history:
                return None

            return f"""{base}
{compare_section}

[유저 상태]
클라우드 미연동 상태. 대화 마지막에 AWS 키 등록 시 실계정 기반 정밀 분석이 가능함을 자연스럽게 안내하세요."""
