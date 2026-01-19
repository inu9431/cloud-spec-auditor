# core/utils/validators.py
from core.exceptions.cloud_exceptions import InvalidCSVFormat


class CloudValidator:
    """클라우드 관련 데이터 검증"""

    @staticmethod
    def validate_csv_headers(df_columns: list):
        required = ["ResourceId", "InstanceType", "Cost"]
        if not all(col in df_columns for col in required):
            raise InvalidCSVFormat(f"필수 컬럼 누락: {required}")

    @staticmethod
    def validate_instance_spec(vcpu: int, memory: float):
        if vcpu <= 0 or memory <= 0:
            raise ValueError("vCPU와 Memory는 양수여야 합니다.")
