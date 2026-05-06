"""
Auth middleware.

Responsibilities:
  1. Block banned users (checked against Redis set).
  2. Upsert user profile on every interaction.
  3. Inject `is_admin` and `is_banned` flags into handler data.
"""
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from api.config import settings
from api.redis_client import get_redis
from api.utils.constants import K_BANNED, K_USER, K_USERS_SET
from api.utils.helpers import jdumps, jloads, now_ts
from api.utils.logger import get_logger

logger = get_logger(__name__)


async def _upsert_user(redis, user) -> None:
    """Create or refresh the user record in Redis."""
    key = K_USER(user.id)
    existing = jloads(await redis.get(key))
    if existing:
        # just refresh username / first_name
        existing["username"]   = user.username or ""
        existing["first_name"] = user.first_name or ""
        await redis.set(key, jdumps(existing))
    else:
        profile = {
            "id":         user.id,
            "username":   user.username or "",
            "first_name": user.first_name or "",
            "joined_at":  now_ts(),
            "uploads":    0,
            "shares":     0,
            "posters":    0,
        }
        pipe = redis.pipeline()
        pipe.set(key, jdumps(profile))
        pipe.sadd(K_USERS_SET(), str(user.id))
        await pipe.execute()


class AuthMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Resolve the acting user
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if not user:
            return await handler(event, data)

        redis = await get_redis()

        # Ban check
        is_banned = await redis.sismember(K_BANNED(), str(user.id))
        if is_banned and user.id != settings.ADMIN_ID:
            if isinstance(event, Message):
                await event.answer("🚫 You have been banned from using this bot.")
            elif isinstance(event, CallbackQuery):
                await event.answer("🚫 You are banned.", show_alert=True)
            return None

        # Upsert profile (fire-and-forget — don't block the handler)
        try:
            await _upsert_user(redis, user)
        except Exception as exc:
            logger.warning("Failed to upsert user %s: %s", user.id, exc)

        # Inject helpers into handler context
        data["is_admin"]  = user.id == settings.ADMIN_ID
        data["is_banned"] = False
        data["redis"]     = redis

        return await handler(event, data)
