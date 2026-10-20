from decimal import Decimal

from apps.costs.models import CloudService

ALL_PROVIDERS = {"AWS", "GCP", "AZURE"}


class InstanceCompareService:

    def compare_by_instance_type(self, instance_type: str, region_normalized: str = None) -> dict:
        """입력된 인스턴스 기준 스펙 조회"""
        base = CloudService.objects.filter(
            instance_type=instance_type,
            is_active=True,
        ).first()

        if not base:
            return {"error": f" '{instance_type}' 인스턴스를 찾을수 없습니다."}

        return self.compare_by_spec(base.vcpu, base.memory_gb, region_normalized)

    def compare_by_spec(self, vcpu: int, memory_gb: Decimal, region_normalized: str = None) -> dict:
        qs = CloudService.objects.filter(
            vcpu=vcpu,
            memory_gb=memory_gb,
            pricing_model="ON_DEMAND",
            is_active=True,
        )

        if region_normalized:
            qs = qs.filter(region_normalized=region_normalized)

        instances = qs.order_by("price_per_hour")

        if not instances.exists():
            return {"error": "해당 스펙의 인스턴스를 찾을수 없습니다"}

        results = [
            {
                "provider": i.provider,
                "instance_type": i.instance_type,
                "region": i.region,
                "region_normalized": i.region_normalized,
                "vcpu": i.vcpu,
                "memory_gb": float(i.memory_gb),
                "cpu_arch": i.cpu_arch,
                "is_burstable": i.is_burstable,
                "price_per_hour": float(i.price_per_hour),
                "price_per_month": float(i.price_per_month),
            }
            for i in instances
        ]

        present_providers = {r["provider"] for r in results}
        missing_providers = sorted(ALL_PROVIDERS - present_providers)

        cheapest = results[0]
        most_expensive = results[-1]
        max_savings = most_expensive["price_per_month"] - cheapest["price_per_month"]

        return {
            "spec": {"vcpu": vcpu, "memory_gb": float(memory_gb)},
            "region_normalized": region_normalized,
            "results": results,
            "missing_providers": missing_providers,
            "summary": {
                "cheapest": cheapest["provider"] + " " + cheapest["instance_type"],
                "max_monthly_savings": round(max_savings, 2),
            },
        }
