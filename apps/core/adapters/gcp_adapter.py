import json
import logging

from google.oauth2 import service_account
from googleapiclient import discovery

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/compute.readonly"]


class GCPAdapter:

    def __init__(self, service_account_json: str, project_id: str):
        sa_info = json.loads(service_account_json)
        credentials = service_account.Credentials.from_service_account_info(sa_info, scopes=SCOPES)

        self.compute = discovery.build("compute", "v1", credentials=credentials)
        self.project_id = project_id

    def get_running_instances(self) -> list[dict]:
        """전체 리전의 실행 중인 VM 인스턴스 목록 반환"""
        instances = []
        try:
            result = (
                self.compute.instances()
                .aggregatedList(
                    project=self.project_id,
                    filter="status=RUNNING",
                )
                .execute()
            )

            for zone_data in result.get("items", {}).values():
                for inst in zone_data.get("instances", []):
                    region = "-".join(inst["zone"].split("/")[-1].split("-")[:-1])
                    instances.append(
                        {
                            "instance_id": inst["id"],
                            "instance_type": inst["machineType"].split("/")[-1],
                            "region": region,
                            "zone": inst["zone"].split("/")[-1],
                            "status": inst["status"],
                        }
                    )
        except Exception as e:
            logger.error("GCP 인스턴스 목록 조회 실패 : error=%s", e)
            raise

        return instances
