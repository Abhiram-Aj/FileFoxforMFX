"""
Security service.

Centralises all permission and ownership checks so handlers stay clean.
"""
from api.config import settings
from api.redis_client import get_redis
from api.services.share_service import get_share
from api.services.poster_service import get_poster
from api.utils.constants import K_BANNED, K_USER, K_USERS_SET
from api.utils.helpers import jloads, jdumps
from api.utils.logger import get_logger

logger = get_logger(__name__)


def is_admin(user_id: int) -> bool:
    return user_id == settings.ADMIN_ID


async def owns_share(user_id: int, share_id: str) -> bool:
    share = await get_share(share_id)
    return share is not None and share.get("owner_id") == user_id


async def owns_poster(user_id: int, poster_id: str) -> bool:
    poster = await get_poster(poster_id)
    return poster is not None and poster.get("owner_id") == user_id


async def ban_user(user_id: int) -> None:
    redis = await get_redis()
    await redis.sadd(K_BANNED(), str(user_id))
    logger.info("Banned user %s", user_id)


async def unban_user(user_id: int) -> None:
    redis = await get_redis()
    await redis.srem(K_BANNED(), str(user_id))
    logger.info("Unbanned user %s", user_id)


async def is_banned(user_id: int) -> bool:
    redis = await get_redis()
    return bool(await redis.sismember(K_BANNED(), str(user_id)))


async def get_user_profile(user_id: int) -> dict | None:
    redis = await get_redis()
    return jloads(await redis.get(K_USER(user_id)))


async def get_all_user_ids() -> list[int]:
    redis = await get_redis()
    members = await redis.smembers(K_USERS_SET())
    return [int(m) for m in members]
