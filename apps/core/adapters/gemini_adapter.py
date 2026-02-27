import json
from typing import Dict

from django.conf import settings

import google.generativeai as genai

from apps.core.exceptions.ai_exceptions import GeminiAPIError


class GeminiAdapter:

    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    def generate_audit(self, inventory_data: Dict, compare_result: Dict) -> Dict:
        try:
            prompt = self._build_audit_prompt(inventory_data, compare_result)
            response = self.model.generate_content(prompt)
            return self._parse_json_response(response.text)
        except GeminiAPIError:
            raise
        except Exception as e:
            raise GeminiAPIError(f"Gemini API 호출 실패: {str(e)}")

    def _build_audit_prompt(self, inventory_data: Dict, compare_result: Dict) -> str:
        """Structured Output을 위한 프롬프트 엔지니어링"""
        return f"""
        당신은 클라우드 비용 최적화 전문가입니다.
  아래 현재 리소스와 3사 비교 데이터를 분석해 최적화 방안을 JSON으로 제시하세요.

  [현재 사용 중인 리소스]
  {json.dumps(inventory_data, ensure_ascii=False, indent=2)}

  [3사 가격 비교]
  {json.dumps(compare_result, ensure_ascii=False, indent=2)}

  반드시 아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
  {{
      "diagnosis": "전체 진단 요약 (2-3문장)",
      "recommendation_type": "SWITCH_PROVIDER 또는 RIGHTSIZING 또는 NO_ACTION",
      "recommended_provider": "AWS 또는 GCP 또는 AZURE",
      "recommended_instance": "인스턴스 타입명",
      "reason": "추천 근거 (구체적인 절감액 포함)",
      "monthly_savings": 숫자
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
        except Exception as e:
            raise GeminiAPIError("Gemini 응답 파싱 실패")
