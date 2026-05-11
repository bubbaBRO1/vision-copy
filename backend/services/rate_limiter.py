import time
from typing import Optional
from config import get_settings

settings = get_settings()

_redis = None


class _MemoryPipeline:
    def __init__(self, redis_obj):
        self.redis_obj = redis_obj
        self.ops = []

    def zremrangebyscore(self, key, _min, _max):
        self.ops.append(("zremrangebyscore", key, _min, _max))

    def zcard(self, key):
        self.ops.append(("zcard", key))

    def zadd(self, key, mapping):
        self.ops.append(("zadd", key, mapping))

    def expire(self, key, ttl):
        self.ops.append(("expire", key, ttl))

    async def execute(self):
        results = []
        for op in self.ops:
            name = op[0]
            if name == "zremrangebyscore":
                results.append(self.redis_obj.zremrangebyscore(*op[1:]))
            elif name == "zcard":
                results.append(self.redis_obj.zcard(*op[1:]))
            elif name == "zadd":
                results.append(self.redis_obj.zadd(*op[1:]))
            elif name == "expire":
                results.append(self.redis_obj.expire(*op[1:]))
        return results


class _MemoryRedis:
    def __init__(self):
        self.sorted_sets: dict[str, list[tuple[str, float]]] = {}

    def pipeline(self):
        return _MemoryPipeline(self)

    def zremrangebyscore(self, key, _min, _max):
        items = self.sorted_sets.get(key, [])
        kept = [(member, score) for member, score in items if not (_min <= score <= _max)]
        removed = len(items) - len(kept)
        self.sorted_sets[key] = kept
        return removed

    def zcard(self, key):
        return len(self.sorted_sets.get(key, []))

    def zadd(self, key, mapping):
        items = self.sorted_sets.setdefault(key, [])
        for member, score in mapping.items():
            items.append((member, score))
        return len(mapping)

    def expire(self, key, ttl):
        return 1


def get_redis():
    global _redis
    if _redis is None:
        try:
            import redis.asyncio as aioredis
            _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        except ModuleNotFoundError:
            _redis = _MemoryRedis()
    return _redis


WINDOW_SECONDS = 86400  # 24h window for daily limits

# limits: (requests_per_day, window_seconds)
ROLE_LIMITS: dict[str, dict[str, tuple[int, int]]] = {
    "admin": {
        "image_search": (999999, WINDOW_SECONDS),
        "ai_query": (999999, WINDOW_SECONDS),
        "deep_research": (999999, WINDOW_SECONDS),
        "api": (999999, 60),
    },
    "pro": {
        "image_search": (100, WINDOW_SECONDS),
        "ai_query": (200, WINDOW_SECONDS),
        "deep_research": (20, WINDOW_SECONDS),
        "api": (60, 60),
    },
    "user": {
        "image_search": (20, WINDOW_SECONDS),
        "ai_query": (50, WINDOW_SECONDS),
        "deep_research": (5, WINDOW_SECONDS),
        "api": (20, 60),
    },
    "anonymous": {
        "image_search": (3, WINDOW_SECONDS),
        "ai_query": (0, WINDOW_SECONDS),
        "deep_research": (0, WINDOW_SECONDS),
        "api": (5, 60),
    },
    "waitlist": {
        "image_search": (0, WINDOW_SECONDS),
        "ai_query": (0, WINDOW_SECONDS),
        "deep_research": (0, WINDOW_SECONDS),
        "api": (0, 60),
    },
}


async def check_rate_limit(
    user_id: Optional[str],
    endpoint: str,
    role: str = "anonymous",
) -> tuple[bool, int, int, int]:
    """Returns (allowed, limit, remaining, reset_ts)"""
    r = get_redis()
    role_key = role if role in ROLE_LIMITS else "anonymous"
    limits = ROLE_LIMITS[role_key]
    limit, window = limits.get(endpoint, (5, 60))

    if limit >= 999999:
        return True, limit, limit, int(time.time()) + window

    if limit == 0:
        return False, 0, 0, int(time.time()) + window

    key = f"rl:{user_id or 'anon'}:{endpoint}"
    now = time.time()
    window_start = now - window

    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)
    pipe.zcard(key)
    pipe.zadd(key, {f"{now}:{id(pipe)}": now})
    pipe.expire(key, window)
    results = await pipe.execute()

    count = results[1]
    allowed = count < limit
    remaining = max(0, limit - count - 1)
    reset_ts = int(now + window)

    return allowed, limit, remaining, reset_ts


async def check_override(user_id: str, endpoint: str, db) -> Optional[int]:
    from sqlalchemy import select, and_
    from models.rate_limit import RateLimitOverride
    from datetime import datetime, timezone
    result = await db.execute(
        select(RateLimitOverride).where(
            and_(
                RateLimitOverride.user_id == user_id,
                RateLimitOverride.endpoint == endpoint,
                (RateLimitOverride.expires_at == None) | (RateLimitOverride.expires_at > datetime.now(timezone.utc)),
            )
        )
    )
    override = result.scalar_one_or_none()
    return override.limit_override if override else None
