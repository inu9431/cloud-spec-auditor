# core/exceptions/cloud_exceptions.py
from core.exceptions.base import BaseAPIException


class CloudServiceNotFound(BaseAPIException):
    status_code = 404
    default_detail = "해당 스펙의 클라우드 서비스를 찾을 수 없습니다."


class CloudWatchConnectionError(BaseAPIException):
    status_code = 503
    default_detail = "AWS CloudWatch 연결에 실패했습니다."


class InvalidCSVFormat(BaseAPIException):
    status_code = 400
    default_detail = "CSV 파일 형식이 올바르지 않습니다."
