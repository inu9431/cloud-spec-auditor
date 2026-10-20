from apps.core.exceptions.base import BaseAPIException


class GeminiAPIError(BaseAPIException):
    status_code = 502
    default_detail = "Gemini API 호출에 실패했습니다."
