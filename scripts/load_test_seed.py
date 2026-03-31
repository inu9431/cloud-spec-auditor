"""
파이프라인 부하 테스트용 더미데이터 시드 스크립트

실행 방법:
    docker compose exec web python scripts/load_test_seed.py

옵션:
    --users   N  : 생성할 유저 수 (기본 10)
    --instances N : 유저당 인스턴스 수 (기본 50)
    --clean      : 기존 더미데이터 삭제 후 재생성

예시:
    docker compose exec web python scripts/load_test_seed.py --users 50 --instances 100
    docker compose exec web python scripts/load_test_seed.py --clean
"""

import argparse
import os
import random
import sys
import time

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "costcut.settings")
django.setup()

from django.db import connection, transaction
from django.utils import timezone

from apps.inventories.models import UserInventory
from apps.users.models import CloudCredential, User

# ── 더미 데이터 풀 ──────────────────────────────────────────────
PROVIDERS = ["AWS", "GCP", "AZURE"]
REGIONS = {
    "AWS": [("ap-northeast-2", "KR"), ("us-east-1", "US_EAST"), ("ap-northeast-1", "JP")],
    "GCP": [("asia-northeast3", "KR"), ("us-east1", "US_EAST"), ("asia-northeast1", "JP")],
    "AZURE": [("koreacentral", "KR"), ("eastus", "US_EAST"), ("japaneast", "JP")],
}
INSTANCE_TYPES = {
    "AWS": ["t3.micro", "t3.small", "t3.medium", "t3.large", "t3.xlarge", "m5.large", "m5.xlarge", "c5.large", "c5.xlarge", "r5.large"],
    "GCP": ["e2-micro", "e2-small", "e2-medium", "e2-standard-2", "e2-standard-4", "n2-standard-2", "n2-standard-4", "c2-standard-4"],
    "AZURE": ["Standard_B1s", "Standard_B2s", "Standard_B4ms", "Standard_D2s_v3", "Standard_D4s_v3", "Standard_F2s_v2"],
}
VCPU_MEMORY = {
    "t3.micro": (2, 1), "t3.small": (2, 2), "t3.medium": (2, 4), "t3.large": (2, 8),
    "t3.xlarge": (4, 16), "m5.large": (2, 8), "m5.xlarge": (4, 16), "c5.large": (2, 4),
    "c5.xlarge": (4, 8), "r5.large": (2, 16),
    "e2-micro": (2, 1), "e2-small": (2, 2), "e2-medium": (2, 4), "e2-standard-2": (2, 8),
    "e2-standard-4": (4, 16), "n2-standard-2": (2, 8), "n2-standard-4": (4, 16),
    "c2-standard-4": (4, 16),
    "Standard_B1s": (1, 1), "Standard_B2s": (2, 4), "Standard_B4ms": (4, 16),
    "Standard_D2s_v3": (2, 8), "Standard_D4s_v3": (4, 16), "Standard_F2s_v2": (2, 4),
}
DUMMY_EMAIL_PREFIX = "loadtest_user_"


def log(msg):
    print(f"[{timezone.now().strftime('%H:%M:%S')}] {msg}")


def clean_dummy_data():
    log("기존 더미데이터 삭제 중...")
    users = User.objects.filter(email__startswith=DUMMY_EMAIL_PREFIX)
    count = users.count()
    users.delete()
    log(f"  삭제 완료: 유저 {count}명 + 연관 데이터 (CASCADE)")


def create_users(n: int) -> list:
    log(f"유저 {n}명 생성 중...")
    users = [
        User(
            email=f"{DUMMY_EMAIL_PREFIX}{i}@loadtest.com",
            is_active=True,
        )
        for i in range(n)
    ]
    for u in users:
        u.set_password("loadtest1234!")

    created = User.objects.bulk_create(users, ignore_conflicts=True)
    log(f"  유저 생성 완료: {len(created)}명")
    return list(User.objects.filter(email__startswith=DUMMY_EMAIL_PREFIX))


def create_credentials(users: list) -> list:
    log(f"CloudCredential 생성 중... ({len(users)}명 × AWS)")
    credentials = [
        CloudCredential(
            user=user,
            provider="AWS",
            credential_type="ACCESS_KEY",
            nickname="loadtest",
            aws_access_key_id="AKIAIOSFODNN7LOADTEST",
            aws_secret_access_key="wJalrXUtnFEMI/K7MDENG/loadtest",
            aws_default_region="ap-northeast-2",
            is_active=True,
            is_verified=True,
        )
        for user in users
    ]
    created = CloudCredential.objects.bulk_create(credentials, ignore_conflicts=True)
    log(f"  Credential 생성 완료: {len(created)}개")
    return list(CloudCredential.objects.filter(user__in=users))


def create_inventories(users: list, instances_per_user: int) -> int:
    log(f"UserInventory 생성 중... ({len(users)}명 × {instances_per_user}개)")

    batch = []
    for user in users:
        provider = random.choice(PROVIDERS)
        instance_pool = INSTANCE_TYPES[provider]
        region_pool = REGIONS[provider]

        for j in range(instances_per_user):
            instance_type = random.choice(instance_pool)
            region, region_normalized = random.choice(region_pool)
            vcpu, memory_gb = VCPU_MEMORY.get(instance_type, (2, 4))

            batch.append(UserInventory(
                user=user,
                provider=provider,
                resource_id=f"i-loadtest-{user.id}-{j:04d}",
                instance_type=instance_type,
                region=region,
                region_normalized=region_normalized,
                vcpu=vcpu,
                memory_gb=memory_gb,
                current_monthly_cost=round(random.uniform(5.0, 500.0), 2),
                cpu_usage_avg=round(random.uniform(1.0, 90.0), 2),
                memory_usage_avg=round(random.uniform(10.0, 80.0), 2),
                is_active=True,
            ))

    CHUNK = 500
    total = 0
    t0 = time.perf_counter()

    for i in range(0, len(batch), CHUNK):
        chunk = batch[i:i + CHUNK]
        UserInventory.objects.bulk_create(chunk, ignore_conflicts=True)
        total += len(chunk)
        elapsed = time.perf_counter() - t0
        log(f"  {total}/{len(batch)}개 적재 ({elapsed:.2f}s)")

    elapsed = time.perf_counter() - t0
    log(f"  UserInventory 생성 완료: {total}개 / {elapsed:.2f}s / {total/elapsed:.0f} rows/s")
    return total


def measure_query_performance():
    log("─── 쿼리 성능 측정 ───")
    with connection.cursor() as cursor:
        queries = [
            (
                "유저별 인벤토리 조회 (user_id=1, is_active=true)",
                "EXPLAIN ANALYZE SELECT * FROM user_inventories WHERE user_id = (SELECT id FROM users LIMIT 1) AND is_active = true",
            ),
            (
                "전체 활성 인벤토리 수",
                "EXPLAIN ANALYZE SELECT COUNT(*) FROM user_inventories WHERE is_active = true",
            ),
            (
                "provider별 집계",
                "EXPLAIN ANALYZE SELECT provider, COUNT(*) FROM user_inventories GROUP BY provider",
            ),
        ]
        for label, sql in queries:
            cursor.execute(sql)
            rows = cursor.fetchall()
            exec_line = next((r[0] for r in rows if "Execution Time" in r[0]), None)
            log(f"  [{label}] {exec_line or '측정 실패'}")


def main():
    parser = argparse.ArgumentParser(description="파이프라인 부하 테스트 더미데이터 시드")
    parser.add_argument("--users", type=int, default=10, help="생성할 유저 수 (기본: 10)")
    parser.add_argument("--instances", type=int, default=50, help="유저당 인스턴스 수 (기본: 50)")
    parser.add_argument("--clean", action="store_true", help="기존 더미데이터 삭제 후 재생성")
    args = parser.parse_args()

    log(f"=== 부하 테스트 시드 시작 (유저 {args.users}명 × 인스턴스 {args.instances}개) ===")
    t_start = time.perf_counter()

    if args.clean:
        clean_dummy_data()

    with transaction.atomic():
        users = create_users(args.users)
        create_credentials(users)
        total_rows = create_inventories(users, args.instances)

    measure_query_performance()

    elapsed = time.perf_counter() - t_start
    log(f"=== 완료: 총 {total_rows}개 인벤토리 / 총 소요 {elapsed:.2f}s ===")
    log(f"    정리: docker compose exec web python scripts/load_test_seed.py --clean")


if __name__ == "__main__":
    main()
