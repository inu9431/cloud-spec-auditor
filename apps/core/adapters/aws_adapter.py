import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from ..exceptions.cloud_exception import CloudWatchConnectionError

logger = logging.getLogger(__name__)


class AWSAdapter:
    def __init__(self, access_key: str, secret_key: str, region: str = "us-east-1"):
        credentials = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "region_name": region,
        }
        self.ec2 = boto3.client("ec2", **credentials)
        self.cost_explorer = boto3.client(
            "ce",
            region_name="us-east-1",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        self.compute_optimizer = boto3.client(
            "compute-optimizer",
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        self.region = region

    def get_running_instances(self) -> List[Dict]:
        """실행 중인 EC2 인스턴스 목록 조회"""
        try:
            response = self.ec2.describe_instances(
                Filters=[{"Name": "instance-state-name", "Values": ["running"]}]
            )
            instances = []
            for reservation in response.get("Reservations", []):
                for inst in reservation.get("Instances", []):
                    instances.append(
                        {
                            "instance_id": inst["InstanceId"],
                            "instance_type": inst["InstanceType"],
                            "region": self.region,
                            "launch_time": inst.get("LaunchTime"),
                        }
                    )
            return instances
        except (BotoCoreError, ClientError) as e:
            raise CloudWatchConnectionError(f"EC2 인스턴스 조회 실패: {str(e)}")

    def get_monthly_cost(self, instance_id: str) -> float:
        """Cost Explorer로 인스턴스별 당월 실제 청구 비용 조회"""
        try:
            now = datetime.now(timezone.utc)
            start = now.replace(day=1).strftime("%Y-%m-%d")
            end = now.strftime("%Y-%m-%d")

            # 1일이면 start=end이므로 전월 fallback
            if start == end:
                prev = now.replace(day=1) - timedelta(days=1)
                start = prev.replace(day=1).strftime("%Y-%m-%d")

            response = self.cost_explorer.get_cost_and_usage(
                TimePeriod={"Start": start, "End": end},
                Granularity="MONTHLY",
                Filter={
                    "Dimensions": {
                        "Key": "RESOURCE_ID",
                        "Values": [instance_id],
                    }
                },
                Metrics=["UnblendedCost"],
                GroupBy=[{"Type": "DIMENSION", "Key": "RESOURCE_ID"}],
            )
            results = response.get("ResultsByTime", [])
            if not results:
                return 0.0
            groups = results[0].get("Groups", [])
            if not groups:
                return 0.0
            return float(groups[0]["Metrics"]["UnblendedCost"]["Amount"])
        except ClientError as e:
            if e.response["Error"]["Code"] in ("AccessDeniedException", "UnauthorizedException"):
                logger.warning("Cost Explorer 권한 없음 — monthly_cost=0.0 반환: %s", instance_id)
                return 0.0
            raise CloudWatchConnectionError(f"Cost Explorer 조회 실패: {str(e)}")
        except BotoCoreError as e:
            raise CloudWatchConnectionError(f"Cost Explorer 조회 실패: {str(e)}")

    def get_monthly_costs_bulk(self, instance_ids: list[str]) -> dict[str, float]:
        """Cost Explorer GroupBy로 여러 인스턴스 비용을 1회 호출로 조회"""
        if not instance_ids:
            return {}
        try:
            now = datetime.now(timezone.utc)
            start = now.replace(day=1).strftime("%Y-%m-%d")
            end = now.strftime("%Y-%m-%d")
            if start == end:
                prev = now.replace(day=1) - timedelta(days=1)
                start = prev.replace(day=1).strftime("%Y-%m-%d")
            response = self.cost_explorer.get_cost_and_usage(
                TimePeriod={"Start": start, "End": end},
                Granularity="MONTHLY",
                Filter={"Dimensions": {"Key": "RESOURCE_ID", "Values": instance_ids}},
                Metrics=["UnblendedCost"],
                GroupBy=[{"Type": "DIMENSION", "Key": "RESOURCE_ID"}],
            )
            results = response.get("ResultsByTime", [])
            if not results:
                return {iid: 0.0 for iid in instance_ids}
            cost_map = {}
            for group in results[0].get("Groups", []):
                iid = group["Keys"][0]
                cost_map[iid] = float(group["Metrics"]["UnblendedCost"]["Amount"])
            return {iid: cost_map.get(iid, 0.0) for iid in instance_ids}
        except ClientError as e:
            if e.response["Error"]["Code"] in ("AccessDeniedException", "UnauthorizedException"):
                logger.warning("Cost Explorer 권한 없음 — 전체 0.0 반환")
                return {iid: 0.0 for iid in instance_ids}
            raise CloudWatchConnectionError(f"Cost Explorer 조회 실패: {str(e)}")
        except BotoCoreError as e:
            raise CloudWatchConnectionError(f"Cost Explorer 조회 실패: {str(e)}")

    def get_rightsizing_recommendations(self, instance_id: str) -> Dict:
        """
        Compute Optimizer로 라이트사이징 추천 조회.
        Compute Optimizer는 AWS 계정에서 사전 활성화 필요 (무료).
        """
        try:
            response = self.compute_optimizer.get_ec2_instance_recommendations(
                instanceArns=[f"arn:aws:ec2:{self.region}::instance/{instance_id}"]
            )
            recommendations = response.get("instanceRecommendations", [])
            if not recommendations:
                return {}

            rec = recommendations[0]
            finding = rec.get(
                "finding", ""
            )  # OVER_PROVISIONED / UNDER_PROVISIONED / OPTIMIZED / NOT_OPTIMIZED
            options = rec.get("recommendationOptions", [])

            best_option = options[0] if options else {}
            return {
                "finding": finding,
                "recommended_instance_type": best_option.get("instanceType", ""),
                "cpu_usage_avg": (
                    rec.get("utilizationMetrics", [{}])[0].get("value", 0.0)
                    if rec.get("utilizationMetrics")
                    else 0.0
                ),
            }
        except (BotoCoreError, ClientError) as e:
            # Compute Optimizer 미활성화 등 오류 시 빈 결과 반환 (필수 아님)
            return {}
