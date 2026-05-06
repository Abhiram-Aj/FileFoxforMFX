"""
Poster service.

Posters live in Redis as JSON blobs under poster:<id>.
The user's poster index is a sorted set: user:<uid>:posters
"""
from typing import Any, Dict, List, Optional

from api.redis_client import get_redis
from api.utils.constants import (
    K_ANALYTICS, K_POSTER, K_USER_POSTERS, K_SHARES_SET
)
from api.utils.helpers import gen_poster_id, jdumps, jloads, now_ts
from api.utils.logger import get_logger

logger = get_logger(__name__)


async def create_poster(
    owner_id: int,
    photo_file_id: str,
    caption: str,
    buttons: List[Dict],
) -> str:
    """Persist a new poster and return its poster_id."""
    redis = await get_redis()
    poster_id = gen_poster_id()

    payload: Dict[str, Any] = {
        "poster_id":    poster_id,
        "owner_id":     owner_id,
        "photo_file_id": photo_file_id,
        "caption":      caption,
        "buttons":      buttons,
        "created_at":   now_ts(),
        "published":    False,
        "published_at": None,
        "channel_id":   None,
        "channel_msg_id": None,
    }

    pipe = redis.pipeline()
    pipe.set(K_POSTER(poster_id), jdumps(payload))
    pipe.zadd(K_USER_POSTERS(owner_id), {poster_id: now_ts()})
    await pipe.execute()

    logger.info("Created poster %s for user %s", poster_id, owner_id)
    return poster_id


async def get_poster(poster_id: str) -> Optional[Dict]:
    redis = await get_redis()
    return jloads(await redis.get(K_POSTER(poster_id)))


async def update_poster(poster_id: str, updates: Dict) -> Optional[Dict]:
    redis = await get_redis()
    data = await get_poster(poster_id)
    if not data:
        return None
    data.update(updates)
    await redis.set(K_POSTER(poster_id), jdumps(data))
    return data


async def mark_published(
    poster_id: str, channel_id: int, channel_msg_id: int
) -> None:
    redis = await get_redis()
    data = await get_poster(poster_id)
    if not data:
        return
    data.update(
        published=True,
        published_at=now_ts(),
        channel_id=channel_id,
        channel_msg_id=channel_msg_id,
    )
    pipe = redis.pipeline()
    pipe.set(K_POSTER(poster_id), jdumps(data))
    pipe.hincrby(K_ANALYTICS(), "poster_publishes", 1)
    await pipe.execute()


async def delete_poster(poster_id: str, owner_id: int) -> bool:
    redis = await get_redis()
    data = await get_poster(poster_id)
    if not data or data["owner_id"] != owner_id:
        return False
    pipe = redis.pipeline()
    pipe.delete(K_POSTER(poster_id))
    pipe.zrem(K_USER_POSTERS(owner_id), poster_id)
    await pipe.execute()
    return True


async def get_user_posters(
    user_id: int, page: int = 1, per_page: int = 10
) -> Dict:
    redis = await get_redis()
    total = await redis.zcard(K_USER_POSTERS(user_id))
    offset = (page - 1) * per_page
    ids = await redis.zrevrange(K_USER_POSTERS(user_id), offset, offset + per_page - 1)

    posters = []
    for pid in ids:
        data = await get_poster(pid)
        if data:
            posters.append(data)

    total_pages = max(1, -(-total // per_page))
    return {"items": posters, "total": total, "page": page, "total_pages": total_pages}
