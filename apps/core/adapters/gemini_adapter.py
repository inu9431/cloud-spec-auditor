from typing import Any, Dict

import google.generativeai as genai
from core.exceptions.ai_exceptions import GeminiAPIError


class GeminiAdapter:
    """Gemini API 통신 어댑터"""

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("models/gemini-2.5-flash")

    def generate_diagnosis(self, inventory_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        사용자 인벤토리 기반 진단 생성
        """
        try:
            prompt = self.build_diagnosis_prompt(inventory_data)
            response = self.model.generate_content(prompt)
            return self.parse_structured_output(response.text)
        except Exception as e:
            raise GeminiAPIError(f" Gemini API 호출 실패 {str(e)}")

    def _build_diagnosis_prompt(self, data: Dict) -> str:
        """Structured Output을 위한 프롬프트 엔지니어링"""
        return f"""
        다음 사용자의 클라우드 리소스 사용 현황을 분석하고,
        JSON형식으로 비용 점감 방안을 제시하세요:

        현재 사용중인 리소스:
        {data}

        응답 형식:
        {{
            "diagnosis": "전체 진단 요약",
            "waste_points": ["낭비 지점1", "낭비 지점2"],
            "total_savings": 123.45
        }}
"""
