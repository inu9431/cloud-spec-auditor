import logging

from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient

logger = logging.getLogger(__name__)


class AzureAdapter:

    def __init__(self, tenant_id: str, client_id: str, client_secret: str, subscription_id: str):
        credentials = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
        self.compute = ComputeManagementClient(credentials, subscription_id)

    def get_running_instances(self) -> list:
        """전체 구독의 실행 중인 VM 인스턴스 목록 반환"""
        instances = []
        try:
            for vm in self.compute.virtual_machines.list_all():
                instance_view = self.compute.virtual_machines.instance_view(
                    vm.id.split("/")[4], vm.name
                )
                statuses = [s.code for s in instance_view.statuses]
                if "PowerState/running" not in statuses:
                    continue

                instances.append(
                    {
                        "instance_id": vm.id,
                        "instance_type": vm.hardware_profile.vm_size,
                        "region": vm.location,
                        "status": "RUNNING",
                    }
                )
        except Exception as e:
            logger.error("Azure 인스턴스 목록 조회 실패: error=%s", e)
            raise

        return instances
