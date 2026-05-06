"""
Analytics service.

All counters live in a single Redis hash (analytics:global).
Per-share download counts are patched directly into the share JSON.
"""
from typing import Dict, Optional

from api.redis_client import get_redis
from api.utils.constants import K_ANALYTICS, K_SHARES_SET, K_USERS_SET
from api.utils.helpers import jloads
from api.utils.logger import get_logger

logger = get_logger(__name__)

_FIELDS = [
    "total_shares", "total_multi", "total_downloads",
    "files_served", "poster_publishes",
]


async def get_global_stats() -> Dict[str, int]:
    redis = await get_redis()
    raw = await redis.hgetall(K_ANALYTICS())
    stats = {f: int(raw.get(f, 0)) for f in _FIELDS}
    # Enrich with live counts
    stats["total_users"]  = await redis.scard(K_USERS_SET())
    stats["active_shares"] = await redis.scard(K_SHARES_SET())
    return stats


async def incr(field: str, amount: int = 1) -> None:
    """Generic increment for any analytics field."""
    redis = await get_redis()
    await redis.hincrby(K_ANALYTICS(), field, amount)


async def record_poster_publish() -> None:
    await incr("poster_publishes")


async def record_download() -> None:
    redis = await get_redis()
    pipe = redis.pipeline()
    pipe.hincrby(K_ANALYTICS(), "total_downloads", 1)
    pipe.hincrby(K_ANALYTICS(), "files_served", 1)
    await pipe.execute()
