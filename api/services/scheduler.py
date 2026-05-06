"""
Scheduler service.

Architecture for Vercel (no persistent processes):
  • Schedules are stored in a Redis Sorted Set  `schedules:queue`
    with the UNIX publish timestamp as the score.
  • A dedicated FastAPI route  /cron  is called by an external cron
    trigger (Vercel Cron Jobs, cron-job.org, etc.) every minute.
  • The /cron handler calls `process_due_schedules()` which pops all
    entries whose score ≤ now and publishes the poster.
"""
import asyncio
from typing import Any, Dict, List, Optional

from aiogram import Bot

from api.redis_client import get_redis
from api.services.media_sender import send_single_file
from api.services.poster_service import get_poster, mark_published
from api.utils.constants import K_SCHEDULE, K_SCHEDULES_QUEUE
from api.utils.helpers import gen_schedule_id, jdumps, jloads, now_ts
from api.utils.logger import get_logger
from api.utils.validators import parse_schedule_dt

logger = get_logger(__name__)


async def create_schedule(
    poster_id: str,
    publish_at_str: str,
    channel_id: int,
    owner_id: int,
) -> Optional[str]:
    """
    Validate datetime string and register in the queue.
    Returns schedule_id on success, None if invalid.
    """
    ok, dt = parse_schedule_dt(publish_at_str)
    if not ok or dt is None:
        return None

    redis     = await get_redis()
    sched_id  = gen_schedule_id()
    publish_ts = int(dt.timestamp())

    payload: Dict[str, Any] = {
        "schedule_id": sched_id,
        "poster_id":   poster_id,
        "publish_at":  publish_ts,
        "channel_id":  channel_id,
        "owner_id":    owner_id,
        "created_at":  now_ts(),
    }

    pipe = redis.pipeline()
    pipe.set(K_SCHEDULE(sched_id), jdumps(payload))
    pipe.zadd(K_SCHEDULES_QUEUE(), {sched_id: publish_ts})
    await pipe.execute()

    logger.info("Scheduled %s → poster %s at %s", sched_id, poster_id, publish_ts)
    return sched_id


async def delete_schedule(sched_id: str) -> None:
    redis = await get_redis()
    pipe = redis.pipeline()
    pipe.delete(K_SCHEDULE(sched_id))
    pipe.zrem(K_SCHEDULES_QUEUE(), sched_id)
    await pipe.execute()


async def list_due_schedules() -> List[Dict]:
    """Return all schedules whose publish_at ≤ now."""
    redis = await get_redis()
    now   = now_ts()
    ids   = await redis.zrangebyscore(K_SCHEDULES_QUEUE(), "-inf", now)
    result = []
    for sid in ids:
        data = jloads(await redis.get(K_SCHEDULE(sid)))
        if data:
            result.append(data)
    return result


async def process_due_schedules(bot: Bot) -> int:
    """
    Called by the /cron endpoint.
    Publishes all due posters and cleans them from the queue.
    Returns the number of schedules processed.
    """
    due = await list_due_schedules()
    processed = 0

    for sched in due:
        sched_id   = sched["schedule_id"]
        poster_id  = sched["poster_id"]
        channel_id = sched["channel_id"]

        try:
            poster = await get_poster(poster_id)
            if not poster:
                logger.warning("Schedule %s: poster %s not found — skipping", sched_id, poster_id)
                await delete_schedule(sched_id)
                continue

            from api.keyboards.reactions import build_reaction_keyboard  # avoid circular
            kb = build_reaction_keyboard(poster_id, {"like": 0, "love": 0, "dislike": 0})

            await bot.send_photo(
                chat_id=channel_id,
                photo=poster["photo_file_id"],
                caption=poster.get("caption", ""),
                parse_mode="HTML",
                reply_markup=kb,
            )
            await mark_published(poster_id, channel_id, channel_msg_id=0)
            await delete_schedule(sched_id)
            processed += 1
            logger.info("Published scheduled poster %s to channel %s", poster_id, channel_id)
        except Exception as exc:
            logger.error("Failed to publish schedule %s: %s", sched_id, exc)

    return processed
