import boto3
from typing import Dict
from core.exceptions.cloud_exception import CloudWatchConnectionError

class AWSAdapter:
    def __init__(self, access_key: str, secret_key: str, region: str = 'us-east-1'):
        self.cludwatch = boto3.client(
            'cloudwatch',
            aws_access_key_id=access_key,
            aws_secret_aceess_key=secret_key,
            region_name=region
        )
    
    def get_instance_metrics(self, instance_id: str) -> Dict[str, float]:
        """
        인스턴스 CPU/Memory 사용률 조회
        """
        try:
            # CloudWatch GetMetricStatistics 호출
            cpu_metric = self.cloudwatch.get_metric_statistics(
                 Namespace='AWS/EC2',
                MetricName='CPUUtilization',
                Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
                StartTime=...,
                EndTime=...,
                Period=3600,
                Statistics=['Average']
            )
            return {
                'cpu_avg': cpu_metric['Datapoints'][0]['Average'],
                'memory_avg': 0.0 # memory 는 CloudWatch Agent 설치 필요
            }
        except Exception as e:
            raise CloudWatchConnectionError(f"CLoudWatch 접근실패: {str(e)}")