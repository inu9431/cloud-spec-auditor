from rest_framework.throttling import UserRateThrottle


class SyncThrottle(UserRateThrottle):
    scope = "sync"


class AuditThrottle(UserRateThrottle):
    scope = "audit"


class PriceSyncThrottle(UserRateThrottle):
    scope = "price_sync"
