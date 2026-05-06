"""
Share service.

Handles all persistence logic for:
  • Single-file shares  (prefix  s_)
  • Multi-file shares   (prefix  m_)
  • Multi-collect sessions (per-user, TTL 1h)
"""
from typing import Any, Dict, List, Optional

from api.redis_client import get_redis
from api.utils.constants import (
    K_MULTI_SESSION, K_SHARE, K_SHARES_SET,
    K_USER, K_USER_SHARES,
    K_ANALYTICS,
    MULTI_SESSION_TTL,
    MAX_MULTI_FILES,
)
from api.utils.helpers import gen_share_id, gen_multi_id, jdumps, jloads, now_ts
from api.utils.logger import get_logger

logger = get_logger(__name__)


# ── Single share ────────────────────────────────────────────────────────────

async def create_share(
    owner_id: int,
    file_info: Dict[str, Any],
    caption: str = "",
) -> str:
    """Persist a single-file share and return its share_id."""
    redis = await get_redis()
    share_id = gen_share_id()

    payload = {
        "type":       "single",
        "owner_id":   owner_id,
        "files":      [file_info],
        "caption":    caption,
        "created_at": now_ts(),
        "downloads":  0,
    }

    pipe = redis.pipeline()
    pipe.set(K_SHARE(share_id), jdumps(payload))
    pipe.zadd(K_USER_SHARES(owner_id), {share_id: now_ts()})
    pipe.sadd(K_SHARES_SET(), share_id)
    # analytics
    pipe.hincrby(K_ANALYTICS(), "total_shares", 1)
    # user counter
    pipe.hincrby(K_USER(owner_id), "shares", 1)
    await pipe.execute()

    logger.info("Created single share %s for user %s", share_id, owner_id)
    return share_id


# ── Multi share ─────────────────────────────────────────────────────────────

async def create_multi_share(owner_id: int, files: List[Dict]) -> str:
    """Persist a multi-file share and return its share_id."""
    redis = await get_redis()
    share_id = gen_multi_id()

    payload = {
        "type":       "multi",
        "owner_id":   owner_id,
        "files":      files,
        "caption":    "",
        "created_at": now_ts(),
        "downloads":  0,
    }

    pipe = redis.pipeline()
    pipe.set(K_SHARE(share_id), jdumps(payload))
    pipe.zadd(K_USER_SHARES(owner_id), {share_id: now_ts()})
    pipe.sadd(K_SHARES_SET(), share_id)
    pipe.hincrby(K_ANALYTICS(), "total_shares", 1)
    pipe.hincrby(K_ANALYTICS(), "total_multi", 1)
    pipe.hincrby(K_USER(owner_id), "shares", 1)
    await pipe.execute()

    logger.info("Created multi share %s (%d files) for user %s", share_id, len(files), owner_id)
    return share_id


# ── Retrieve ────────────────────────────────────────────────────────────────

async def get_share(share_id: str) -> Optional[Dict]:
    redis = await get_redis()
    return jloads(await redis.get(K_SHARE(share_id)))


async def increment_downloads(share_id: str) -> None:
    redis = await get_redis()
    pipe = redis.pipeline()
    pipe.hincrby(K_SHARE(share_id), "downloads", 1)   # won't work on JSON str
    pipe.hincrby(K_ANALYTICS(), "total_downloads", 1)
    pipe.hincrby(K_ANALYTICS(), "files_served", 1)
    await pipe.execute()

    # Also patch the JSON payload's download counter
    raw = await redis.get(K_SHARE(share_id))
    data = jloads(raw)
    if data:
        data["downloads"] = data.get("downloads", 0) + 1
        await redis.set(K_SHARE(share_id), jdumps(data))


async def delete_share(share_id: str, owner_id: int) -> bool:
    redis = await get_redis()
    existing = await get_share(share_id)
    if not existing or existing["owner_id"] != owner_id:
        return False
    pipe = redis.pipeline()
    pipe.delete(K_SHARE(share_id))
    pipe.zrem(K_USER_SHARES(owner_id), share_id)
    pipe.srem(K_SHARES_SET(), share_id)
    await pipe.execute()
    return True


async def admin_delete_share(share_id: str) -> bool:
    redis = await get_redis()
    existing = await get_share(share_id)
    if not existing:
        return False
    owner_id = existing.get("owner_id", 0)
    pipe = redis.pipeline()
    pipe.delete(K_SHARE(share_id))
    pipe.zrem(K_USER_SHARES(owner_id), share_id)
    pipe.srem(K_SHARES_SET(), share_id)
    await pipe.execute()
    return True


# ── User share listing ──────────────────────────────────────────────────────

async def get_user_shares(user_id: int, page: int = 1, per_page: int = 10) -> Dict:
    redis = await get_redis()
    total = await redis.zcard(K_USER_SHARES(user_id))
    offset = (page - 1) * per_page
    ids = await redis.zrevrange(K_USER_SHARES(user_id), offset, offset + per_page - 1)

    shares = []
    for sid in ids:
        data = await get_share(sid)
        if data:
            shares.append({"id": sid, **data})

    total_pages = max(1, -(-total // per_page))
    return {"items": shares, "total": total, "page": page, "total_pages": total_pages}


# ── Multi-collect session ────────────────────────────────────────────────────

async def session_start(user_id: int) -> None:
    redis = await get_redis()
    payload = {"files": [], "started_at": now_ts()}
    await redis.set(K_MULTI_SESSION(user_id), jdumps(payload), ex=MULTI_SESSION_TTL)


async def session_add_file(user_id: int, file_info: Dict) -> int:
    """Add file to ongoing multi session.  Returns new file count or -1 if over limit."""
    redis = await get_redis()
    raw = await redis.get(K_MULTI_SESSION(user_id))
    data = jloads(raw) or {"files": [], "started_at": now_ts()}
    if len(data["files"]) >= MAX_MULTI_FILES:
        return -1
    data["files"].append(file_info)
    await redis.set(K_MULTI_SESSION(user_id), jdumps(data), ex=MULTI_SESSION_TTL)
    return len(data["files"])


async def session_get(user_id: int) -> Optional[Dict]:
    redis = await get_redis()
    return jloads(await redis.get(K_MULTI_SESSION(user_id)))


async def session_clear(user_id: int) -> None:
    redis = await get_redis()
    await redis.delete(K_MULTI_SESSION(user_id))
