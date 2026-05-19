from decimal import Decimal

from apps.core.adapters.gemini_adapter import GeminiAdapter
from apps.core.exceptions.ai_exceptions import GeminiAPIError
from apps.costs.models import CloudService
from apps.costs.services.compare_service import InstanceCompareService
from apps.inventories.models import UserInventory
from apps.recommendations.models import Recommendation, RecommendationItem

_RIGHTSIZING_CPU_THRESHOLD = 30.0


class AuditService:

    def audit(self, inventory_id: int, user) -> dict:
        try:
            inventory = UserInventory.objects.get(id=inventory_id, user=user, is_active=True)
        except UserInventory.DoesNotExist:
            return {"error": "인벤토리를 찾을수 없습니다"}

        cpu_usage = float(inventory.cpu_usage_avg) if inventory.cpu_usage_avg else None
        analysis_type = (
            "RIGHTSIZING"
            if cpu_usage is not None and cpu_usage < _RIGHTSIZING_CPU_THRESHOLD
            else "SWITCH_PROVIDER"
        )

        if analysis_type == "RIGHTSIZING":
            compare_result = InstanceCompareService().compare_by_spec(
                vcpu=max(1, inventory.vcpu // 2),
                memory_gb=inventory.memory_gb / 2,
                region_normalized=inventory.region_normalized,
            )
        else:
            compare_result = InstanceCompareService().compare_by_spec(
                vcpu=inventory.vcpu,
                memory_gb=inventory.memory_gb,
                region_normalized=inventory.region_normalized,
            )

        if "error" in compare_result:
            return compare_result

        current_cost = inventory.current_monthly_cost

        # 현재 provider 제외, cpu_arch 일치, 버스터블 혼용 방지
        current_service = CloudService.objects.filter(
            provider=inventory.provider,
            instance_type=inventory.instance_type,
        ).first()
        current_arch = current_service.cpu_arch if current_service else "x86_64"
        current_burstable = current_service.is_burstable if current_service else False

        alternatives = [
            r for r in compare_result["results"]
            if r["provider"] != inventory.provider
            and r["cpu_arch"] == current_arch
            and r["is_burstable"] == current_burstable
        ]

        # arch/burstable 조건 완화 fallback
        if not alternatives:
            alternatives = [
                r for r in compare_result["results"]
                if r["provider"] != inventory.provider
            ]
        if not alternatives:
            return {"error": "비교 가능한 타 provider 인스턴스가 없습니다"}

        best_alternative = alternatives[0]
        optimized_cost = Decimal(str(best_alternative["price_per_month"]))
        total_savings = current_cost - optimized_cost
        saving_amount = float(total_savings)

        inventory_data = {
            "provider": inventory.provider,
            "instance_type": inventory.instance_type,
            "vcpu": inventory.vcpu,
            "memory_gb": float(inventory.memory_gb),
            "region": inventory.region_normalized,
            "current_monthly_cost": float(current_cost),
            "cpu_usage_avg": cpu_usage,
            "analysis_type": analysis_type,
        }

        try:
            ai_result = GeminiAdapter().generate_audit(
                inventory_data, compare_result, saving_amount, analysis_type
            )
        except GeminiAPIError:
            ai_result = {
                "diagnosis": (
                    f"CPU 사용률 {cpu_usage}% 기준 과스펙이 감지되었습니다."
                    if cpu_usage is not None
                    else "3사 가격 비교 기반 provider 전환을 추천합니다."
                ),
                "recommendation_type": analysis_type,
                "recommended_provider": best_alternative["provider"],
                "recommended_instance": best_alternative["instance_type"],
                "reason": f"월 ${saving_amount:.2f} USD 절감 가능. On-Demand 기준이며 Reserved/Spot 적용 시 추가 절감 가능합니다.",
            }

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
                region_normalized=option["region_normalized"],
            ).first()
            if cloud_service is None:
                continue
            expected_cost = Decimal(str(option["price_per_month"]))
            RecommendationItem.objects.create(
                recommendation=recommendation,
                recommended_service=cloud_service,
                recommendation_type=ai_result.get("recommendation_type", analysis_type),
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
            "analysis_type": analysis_type,
            "current": {
                "provider": inventory.provider,
                "instance_type": inventory.instance_type,
                "monthly_cost": float(current_cost),
                "cpu_arch": current_arch,
                "is_burstable": current_burstable,
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
