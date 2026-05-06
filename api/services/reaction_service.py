"""
Reaction service.

Each reaction type is stored as a Redis Set of user_ids:
  reactions:<poster_id>:like
  reactions:<poster_id>:love
  reactions:<poster_id>:dislike

Vote rules:
  • User can hold at most ONE reaction at a time.
  • Voting the same type again toggles it OFF (remove).
  • Voting a different type switches the vote.
"""
from typing import Dict, Optional, Tuple

from api.redis_client import get_redis
from api.utils.constants import K_REACTIONS, REACTION_KEYS, REACTION_EMOJI
from api.utils.logger import get_logger

logger = get_logger(__name__)


async def get_counts(poster_id: str) -> Dict[str, int]:
    """Return current reaction counts for a poster."""
    redis = await get_redis()
    counts = {}
    for key in REACTION_KEYS:
        counts[key] = await redis.scard(K_REACTIONS(poster_id, key))
    return counts


async def get_user_reaction(poster_id: str, user_id: int) -> Optional[str]:
    """Return which reaction key the user currently holds, or None."""
    redis = await get_redis()
    uid = str(user_id)
    for key in REACTION_KEYS:
        if await redis.sismember(K_REACTIONS(poster_id, key), uid):
            return key
    return None


async def toggle_reaction(
    poster_id: str, user_id: int, reaction_key: str
) -> Tuple[Dict[str, int], Optional[str]]:
    """
    Toggle a reaction for a user.

    Returns:
        (updated_counts, new_user_reaction)  — new_user_reaction is None if toggled off.
    """
    if reaction_key not in REACTION_KEYS:
        raise ValueError(f"Invalid reaction key: {reaction_key}")

    redis = await get_redis()
    uid = str(user_id)

    # Find current reaction
    current = await get_user_reaction(poster_id, user_id)

    pipe = redis.pipeline()
    if current == reaction_key:
        # Toggle off
        pipe.srem(K_REACTIONS(poster_id, reaction_key), uid)
        new_reaction = None
    else:
        # Remove old vote if any
        if current:
            pipe.srem(K_REACTIONS(poster_id, current), uid)
        # Add new vote
        pipe.sadd(K_REACTIONS(poster_id, reaction_key), uid)
        new_reaction = reaction_key
    await pipe.execute()

    counts = await get_counts(poster_id)
    return counts, new_reaction


def format_reaction_bar(counts: Dict[str, int], user_reaction: Optional[str] = None) -> str:
    """
    Build a human-readable reaction summary.
    Example: 👍 12  ❤️ 4  👎 1
    """
    parts = []
    for key in REACTION_KEYS:
        emoji = REACTION_EMOJI[key]
        count = counts.get(key, 0)
        marker = "·" if user_reaction == key else ""
        parts.append(f"{emoji}{marker} {count}")
    return "  ".join(parts)
