from rest_framework import status
from rest_framework.exceptions import APIException

# 예시 커스텀 에러 만들떄


class BaseAPIException(APIException):
    """모든 커스텀 예외의 베이스 클래스"""

    status_code = 500
    default_detail = "서버 오류가 발생했습니다"
    default_code = "server_error"

class GeminiAPIError(BaseAPIException):
    status_code = 502
    default_detail= "Gemini API 호출에 실패했습니다"