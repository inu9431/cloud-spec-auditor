# core/utils/cache_helper.py
import json
from typing import Any, Callable, Optional

from django.core.cache import cache


class CacheHelper:
    """Redis 캐싱 헬퍼"""

    @staticmethod
    def get_or_set(key: str, fetch_func: Callable, timeout: int = 3600) -> Any:
        """
        캐시 조회 후 없으면 fetch_func 실행하여 저장
        """
        cached = cache.get(key)
        if cached:
            return json.loads(cached)

        data = fetch_func()
        cache.set(key, json.dumps(data), timeout)
        return data

    @staticmethod
    def invalidate_pattern(pattern: str):
        """특정 패턴의 캐시 전체 삭제 (e.g., 'user:123:*')"""
        # Redis SCAN 명령어 사용
        pass
