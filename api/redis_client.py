"""
Async Redis client.
• Single connection pool shared across the entire serverless instance.
• Works with Upstash (rediss://) and self-hosted Redis (redis://).
• Decode responses = True so everything is str/dict friendly.
"""
import logging
from typing import Optional

import redis.asyncio as aioredis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff

from api.config import settings

logger = logging.getLogger(__name__)

_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Return the shared Redis connection, creating it if necessary."""
    global _redis
    if _redis is None:
        retry = Retry(ExponentialBackoff(cap=3, base=0.5), retries=3)
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry=retry,
            retry_on_timeout=True,
            health_check_interval=30,
            max_connections=20,
        )
        logger.info("Redis connection pool initialised")
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None
        logger.info("Redis connection closed")
