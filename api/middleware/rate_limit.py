"""
Aiogram v3 rate-limit middleware.

Enforces per-user limits using Redis INCR + EXPIRE:
  • general  : 10 requests / 15 s
  • multi    : 3  requests / 60 s
  • poster   : 5  requests / 60 s

Admins bypass all limits.
"""
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from api.config import settings
from api.redis_client import get_redis
from api.utils.constants import (
    K_RL,
    RL_GENERAL_MAX, RL_GENERAL_WINDOW,
    RL_MULTI_MAX,   RL_MULTI_WINDOW,
    RL_POSTER_MAX,  RL_POSTER_WINDOW,
)
from api.utils.logger import get_logger

logger = get_logger(__name__)

# Map command prefix → (max, window_seconds, bucket_name)
_CMD_LIMITS: Dict[str, tuple] = {
    "/multi":  (RL_MULTI_MAX,  RL_MULTI_WINDOW,  "multi"),
    "/poster": (RL_POSTER_MAX, RL_POSTER_WINDOW, "poster"),
}


class RateLimitMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Only rate-limit Message events with a from_user
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id

        # Admin bypass
        if user_id == settings.ADMIN_ID:
            return await handler(event, data)

        redis = await get_redis()

        # Determine which bucket this message falls into
        text = (event.text or "").strip()
        bucket, max_req, window = "general", RL_GENERAL_MAX, RL_GENERAL_WINDOW
        for prefix, (lim, win, bkt) in _CMD_LIMITS.items():
            if text.startswith(prefix):
                bucket, max_req, window = bkt, lim, win
                break

        key = K_RL(user_id, bucket)
        pipe = redis.pipeline()
        pipe.incr(key)
        pipe.ttl(key)
        count, ttl = await pipe.execute()

        if count == 1:
            await redis.expire(key, window)
            ttl = window

        if count > max_req:
            wait = ttl if ttl > 0 else window
            await event.answer(
                f"⏳ Slow down. Try again in <b>{wait}</b> seconds.",
                parse_mode="HTML",
            )
            logger.warning("Rate-limited user=%s bucket=%s count=%s", user_id, bucket, count)
            return None   # swallow the update

        return await handler(event, data)
