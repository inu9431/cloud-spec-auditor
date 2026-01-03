from rest_framework.exceptions import APIException
from rest_framework import status

# 예시 커스텀 에러 만들떄
"""
class ConflictException(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "이미 존재하는 값입니다."
    default_code = "conflict"
"""