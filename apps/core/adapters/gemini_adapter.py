import json
from typing import Dict

from django.conf import settings

import google.generativeai as genai

from apps.core.exceptions.ai_exceptions import GeminiAPIError


class GeminiAdapter:

    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    def generate_audit(
        self, inventory_data: Dict, compare_result: Dict, saving_amount: float
    ) -> Dict:
        try:
            prompt = self._build_audit_prompt(inventory_data, compare_result, saving_amount)
            response = self.model.generate_content(prompt)
            return self._parse_json_response(response.text)
        except GeminiAPIError:
            raise
        except Exception as e:
            raise GeminiAPIError(f"Gemini API 호출 실패: {str(e)}")

    def _build_audit_prompt(
        self, inventory_data: Dict, compare_result: Dict, saving_amount: float
    ) -> str:
        """Structured Output을 위한 프롬프트 엔지니어링"""
        cpu_usage = inventory_data.get("cpu_usage_avg")

        if cpu_usage is not None:
            usage_section = f"CPU 평균 사용률: {cpu_usage}% (AWS Compute Optimizer 분석 기준)"
            analysis_note = "CPU 사용률 데이터를 기반으로 과스펙 여부를 판단하세요."
        else:
            usage_section = "CPU 사용률: 데이터 없음 (Compute Optimizer 미활성화 상태)"
            analysis_note = "사용률 데이터가 없으므로 과스펙 판단은 하지 말고, 3사 가격 비교 기반의 provider 전환 절감만 제시하세요."

        return f"""
  당신은 클라우드 비용 최적화 전문가입니다.
  아래 현재 리소스와 3사 비교 데이터를 분석해 최적화 방안을 JSON으로 제시하세요.

  [현재 사용 중인 리소스]
  {json.dumps(inventory_data, ensure_ascii=False, indent=2)}

  [사용률]
  {usage_section}

  [분석 지침]
  {analysis_note}

  [3사 가격 비교]
  {json.dumps(compare_result, ensure_ascii=False, indent=2)}

  [Python이 계산한 예상 월 절감액]
  ${saving_amount:.2f} USD

  ※ 주의: 위 가격 비교는 On-Demand 기준입니다.
  Reserved(1년 약 40% 절감) 또는 Spot(약 70% 절감, 중단 가능) 적용 시
  실제 절감폭은 더 커질 수 있습니다. 추천 이유에 이 점을 언급하세요.

  반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
  {{
      "diagnosis": "전체 진단 요약 (2-3문장)",
      "recommendation_type": "SWITCH_PROVIDER 또는 RIGHTSIZING 또는 NO_ACTION",
      "recommended_provider": "AWS 또는 GCP 또는 AZURE",
      "recommended_instance": "인스턴스 타입명",
      "reason": "추천 근거 (절감액 ${saving_amount:.2f} USD/월 기준으로 설명)"
  }}
  """

    def _parse_json_response(self, text: str) -> Dict:
        try:
            cleaned = text.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
            return json.loads(cleaned.strip())
        except Exception:
            raise GeminiAPIError("Gemini 응답 파싱 실패")

    def generate_consult_spec(self, description: str) -> Dict:
        """1단계 기획 설명 -> 서버 스펙 추정 (Json 구조화)"""
        try:
            prompt = self._build_consult_spec_prompt(description)
            response = self.model.generate_content(prompt)
            return self._parse_json_response(response.text)
        except GeminiAPIError:
            raise
        except Exception as e:
            raise GeminiAPIError(f" 스펙 추정 실패 {str(e)}")

    def generate_consult_explain(self, description: str, spec: Dict, compare_result: Dict) -> Dict:
        """2단계: 스펙 + 비교 결과 -> 자연어 설명 생성"""
        try:
            prompt = self._build_consult_explain_prompt(description, spec, compare_result)
            response = self.model.generate_content(prompt)
            return self._parse_json_response(response.text)
        except GeminiAPIError:
            raise
        except Exception as e:
            raise GeminiAPIError(f"설명 생성 실패: {str(e)}")

    def _build_consult_spec_prompt(self, description: str) -> str:
        """1단계 프롬프트: 기획 → 스펙 + 리전 추정만 담당"""
        return f"""
당신은 클라우드 인프라 설계 전문가입니다.
아래 서비스 기획을 분석해서 필요한 서버 스펙과 적합한 리전을 JSON으로 추정하세요.

[서비스 기획]
{description}

[스펙 추정 기준]
- 정적 웹사이트/랜딩페이지: vcpu=1, memory_gb=1, storage_gb=20
- 소규모 서비스 (동시접속 100명 이하): vcpu=2, memory_gb=2, storage_gb=30
- 쇼핑몰/커머스 (동시접속 1,000명): vcpu=2, memory_gb=4, storage_gb=50
- 중규모 서비스 (동시접속 1,000~5,000명): vcpu=4, memory_gb=8, storage_gb=100
- 대규모 서비스 (동시접속 5,000명 이상): vcpu=8, memory_gb=16, storage_gb=200
- 이미지/동영상 많은 서비스: storage_gb 2배 추가
- 실시간 채팅/알림 포함: vcpu 1 추가
- AI/ML 기능 포함: vcpu 4 이상, memory_gb 8 이상

[리전 추정 기준]
- 한국 서비스/한국 유저 타겟: KR
- 일본 서비스/일본 유저 타겟: JP
- 글로벌 서비스 또는 비용 최적화 우선: US_EAST (미국 동부가 가장 저렴)
- 동남아 타겟: SG
- 유럽 타겟: EU_WEST
- 특별한 언급 없으면 비용 기준 US_EAST 권장

반드시 아래 JSON 형식으로만 응답하세요 (마크다운, 설명 텍스트 없이 JSON만):
{{
    "vcpu": 숫자,
    "memory_gb": 숫자,
    "storage_gb": 숫자,
    "region": "KR 또는 JP 또는 US_EAST 또는 SG 또는 EU_WEST 중 하나",
    "reason": "스펙 및 리전 추정 근거 (1-2문장)"
}}
"""

    def _build_consult_explain_prompt(self, description: str, spec: Dict, compare_result: Dict) -> str:
        """2단계 프롬프트: 스펙 + 가격비교 결과 → 유저 설명만 담당. 숫자 계산 금지."""
        return f"""
당신은 클라우드 비용 최적화 전문가입니다.
아래 분석 결과를 유저에게 친절하게 설명하세요.
숫자는 절대 변경하지 마세요. 스펙 추정이나 가격 계산은 이미 완료된 상태입니다.

[유저 서비스 기획]
{description}

[추정된 서버 스펙]
- vCPU: {spec['vcpu']}코어
- 메모리: {spec['memory_gb']}GB
- 스토리지: {spec['storage_gb']}GB
- 추정 리전: {spec['region']}
- 추정 근거: {spec['reason']}

[3사 가격 비교 결과 (Python이 DB에서 조회한 실제 데이터)]
{json.dumps(compare_result, ensure_ascii=False, indent=2)}

반드시 아래 JSON 형식으로만 응답하세요 (마크다운, 설명 텍스트 없이 JSON만):
{{
    "summary": "서비스 분석 요약 (2-3문장)",
    "recommended_provider": "AWS 또는 GCP 또는 AZURE",
    "recommended_instance": "인스턴스 타입명",
    "reason": "추천 근거 (On-Demand 기준이며 Reserved/Spot 절감 가능성 언급)",
    "architecture_tips": "추가 아키텍처 제안 (CDN, 오토스케일링 등, 1-2문장)"
}}
"""

