from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist

from apps.core.adapters.gemini_adapter import GeminiAdapter
from apps.costs.models import CloudService
from apps.costs.services.compare_service import InstanceCompareService
from apps.inventories.models import UserInventory
from apps.recommendations.models import Recommendation, RecommendationItem


class AuditService:

    def audit(self, inventory_id: int, user) -> dict:
        # 1. 인벤토리 조회
        try:
            inventory = UserInventory.objects.get(id=inventory_id, user=user, is_active=True)
        except UserInventory.DoesNotExist:
            return {"error": "인벤토리를 찾을수 없습니다"}

        # 같은 스펙 3사 비교
        compare_result = InstanceCompareService().compare_by_spec(
            vcpu=inventory.vcpu,
            memory_gb=inventory.memory_gb,
            region_normalized=inventory.region_normalized,
        )
        if "error" in compare_result:
            return compare_result

        # Gemini 호출
        inventory_data = {
            "provider": inventory.provider,
            "instance_type": inventory.instance_type,
            "vcpu": inventory.vcpu,
            "memory_gb": float(inventory.memory_gb),
            "region": inventory.region_normalized,
            "current_monthly_cost": float(inventory.current_monthly_cost),
            "cpu_usage_avg": float(inventory.cpu_usage_avg) if inventory.cpu_usage_avg else None,
        }
        ai_result = GeminiAdapter().generate_audit(inventory_data, compare_result)

        # DB 저장
        current_cost = inventory.current_monthly_cost
        optimized_cost = Decimal(str(compare_result["results"][0]["price_per_month"]))
        total_savings = current_cost - optimized_cost

        recommendation = Recommendation.objects.create(
            user=user,
            inventory=inventory,
            status=Recommendation.Status.COMPLETED,
            total_current_cost=current_cost,
            total_optimized_cost=optimized_cost,
            total_savings=total_savings,
            diagnosis_summary=ai_result.get("diagnosis", ""),
        )

        for idx, option in enumerate(compare_result["results"]):
            if option["provider"] == inventory.provider:
                continue
            cloud_service = CloudService.objects.filter(
                provider=option["provider"],
                instance_type=option["instance_type"],
                region=option["region"],
            ).first()
            expected_cost = Decimal(str(option["price_per_month"]))
            RecommendationItem.objects.create(
                recommendation=recommendation,
                recommended_service=cloud_service,
                recommendation_type=ai_result.get("recommendation_type", "SWITCH_PROVIDER"),
                original_provider=inventory.provider,
                original_instance_type=inventory.instance_type,
                original_monthly_cost=current_cost,
                original_cpu_usage=inventory.cpu_usage_avg,
                expected_monthly_cost=expected_cost,
                savings_amount=current_cost - expected_cost,
                savings_percentage=(
                    (current_cost - expected_cost) / current_cost * 100 if current_cost > 0 else 0
                ),
                reason=ai_result.get("reason", ""),
                priority=idx + 1,
            )

        return {
            "recommendation_id": recommendation.id,
            "diagnosis": ai_result.get("diagnosis"),
            "current": {
                "provider": inventory.provider,
                "instance_type": inventory.instance_type,
                "monthly_cost": float(current_cost),
            },
            "recommended": {
                "provider": ai_result.get("recommended_provider"),
                "instance_type": ai_result.get("recommended_instance"),
                "monthly_cost": float(optimized_cost),
            },
            "monthly_savings": float(total_savings),
            "reason": ai_result.get("reason"),
            "compare_result": compare_result,
        }
