"""
Single source of truth for every constant and Redis key template.
Import from here — never hard-code keys anywhere else.
"""

# ── Limits ────────────────────────────────────────────────────────────────
MAX_MULTI_FILES: int = 50
ITEMS_PER_PAGE: int = 10
MEDIA_GROUP_SIZE: int = 10          # Telegram max per sendMediaGroup call
MAX_CAPTION_LEN: int = 1024
MAX_BUTTON_TEXT: int = 64
MAX_POSTER_BUTTONS: int = 3
SHARE_ID_LEN: int = 8
POSTER_ID_LEN: int = 8
SCHEDULE_ID_LEN: int = 8
MULTI_SESSION_TTL: int = 3600        # 1 hour
SCHEDULE_LOOKAHEAD: int = 300        # check schedules due in next 5 min

# ── Rate limits ───────────────────────────────────────────────────────────
RL_GENERAL_MAX: int = 10
RL_GENERAL_WINDOW: int = 15          # seconds
RL_MULTI_MAX: int = 3
RL_MULTI_WINDOW: int = 60
RL_POSTER_MAX: int = 5
RL_POSTER_WINDOW: int = 60

# ── File types ────────────────────────────────────────────────────────────
SUPPORTED_FILE_TYPES = frozenset(
    ["document", "video", "photo", "audio", "voice",
     "animation", "video_note", "sticker"]
)
MEDIA_GROUP_TYPES = frozenset(["photo", "video"])   # types usable in a media group

# ── Reactions ─────────────────────────────────────────────────────────────
REACTION_EMOJI = {"like": "👍", "love": "❤️", "dislike": "👎"}
REACTION_KEYS = list(REACTION_EMOJI.keys())

# ── Redis key templates ───────────────────────────────────────────────────
# format(**kwargs) or .format(id=...) style

def K_SHARE(share_id: str)      -> str: return f"share:{share_id}"
def K_POSTER(poster_id: str)    -> str: return f"poster:{poster_id}"
def K_USER(user_id: int)        -> str: return f"user:{user_id}"
def K_USER_SHARES(uid: int)     -> str: return f"user:{uid}:shares"
def K_USER_POSTERS(uid: int)    -> str: return f"user:{uid}:posters"
def K_REACTIONS(pid: str, key: str) -> str: return f"reactions:{pid}:{key}"
def K_ANALYTICS()               -> str: return "analytics:global"
def K_RL(uid: int, kind: str)   -> str: return f"rl:{uid}:{kind}"
def K_SCHEDULE(sid: str)        -> str: return f"schedule:{sid}"
def K_SCHEDULES_QUEUE()         -> str: return "schedules:queue"
def K_MULTI_SESSION(uid: int)   -> str: return f"session:multi:{uid}"
def K_USERS_SET()               -> str: return "users"
def K_SHARES_SET()              -> str: return "shares"
def K_BANNED()                  -> str: return "banned_users"
