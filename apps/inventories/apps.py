from django.apps import AppConfig


class InventoriesConfig(AppConfig):
    name = "apps.inventories"

    def ready(self):
        self._register_schedules()

    def _register_schedules(self):
        """django-q2 스케줄 등록 (중복 방지)"""
        try:
            from django_q.models import Schedule

            # 24h 인벤토리 자동 수집 + audit
            Schedule.objects.get_or_create(
                func="pipeline.flows.inventory_flow.sync_all_inventories",
                defaults={
                    "name": "24h 인벤토리 자동 수집",
                    "schedule_type": Schedule.HOURS,
                    "hours": 24,
                    "repeats": -1,  # 무한 반복
                },
            )

            # 주 1회 3사 가격 최신화
            Schedule.objects.get_or_create(
                func="pipeline.flows.inventory_flow.sync_cloud_prices",
                defaults={
                    "name": "주 1회 3사 가격 sync",
                    "schedule_type": Schedule.WEEKLY,
                    "repeats": -1,
                },
            )
        except Exception:
            # 마이그레이션 전 등 DB가 준비되지 않은 경우 무시
            pass
