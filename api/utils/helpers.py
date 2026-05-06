"""
Stateless helper utilities — no Redis, no bot dependencies.
"""
import json
import secrets
import string
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from api.utils.constants import SHARE_ID_LEN, POSTER_ID_LEN, SCHEDULE_ID_LEN


# ── ID generation ──────────────────────────────────────────────────────────

_ALPHABET = string.ascii_letters + string.digits


def _rand(n: int) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(n))


def gen_share_id() -> str:    return f"s_{_rand(SHARE_ID_LEN)}"
def gen_multi_id() -> str:    return f"m_{_rand(SHARE_ID_LEN)}"
def gen_poster_id() -> str:   return f"p_{_rand(POSTER_ID_LEN)}"
def gen_schedule_id() -> str: return f"sch_{_rand(SCHEDULE_ID_LEN)}"


# ── Time helpers ───────────────────────────────────────────────────────────

def now_ts() -> int:
    return int(time.time())


def ts_to_utc(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def fmt_ts(ts: int) -> str:
    return ts_to_utc(ts).strftime("%Y-%m-%d %H:%M UTC")


# ── JSON helpers ───────────────────────────────────────────────────────────

def jdumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def jloads(raw: Optional[str]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


# ── Formatting ─────────────────────────────────────────────────────────────

def fmt_size(size_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} TB"


def chunk_list(lst: List, size: int) -> List[List]:
    return [lst[i : i + size] for i in range(0, len(lst), size)]


# ── File extraction from Telegram Message ─────────────────────────────────

def extract_file(msg) -> Optional[Dict[str, Any]]:
    """
    Pull file_id + metadata from any Telegram message type.
    Returns None if the message carries no supported file.
    """
    if msg.document:
        d = msg.document
        return dict(
            file_id=d.file_id, file_type="document",
            file_name=d.file_name or "file",
            file_size=d.file_size or 0,
            mime_type=d.mime_type or "",
        )
    if msg.video:
        v = msg.video
        return dict(
            file_id=v.file_id, file_type="video",
            file_name=v.file_name or "video.mp4",
            file_size=v.file_size or 0,
            mime_type=v.mime_type or "video/mp4",
        )
    if msg.photo:
        p = msg.photo[-1]          # largest size
        return dict(
            file_id=p.file_id, file_type="photo",
            file_name="photo.jpg",
            file_size=p.file_size or 0,
            mime_type="image/jpeg",
        )
    if msg.audio:
        a = msg.audio
        return dict(
            file_id=a.file_id, file_type="audio",
            file_name=a.file_name or "audio.mp3",
            file_size=a.file_size or 0,
            mime_type=a.mime_type or "audio/mpeg",
        )
    if msg.voice:
        return dict(
            file_id=msg.voice.file_id, file_type="voice",
            file_name="voice.ogg",
            file_size=msg.voice.file_size or 0,
            mime_type="audio/ogg",
        )
    if msg.animation:
        an = msg.animation
        return dict(
            file_id=an.file_id, file_type="animation",
            file_name=an.file_name or "animation.mp4",
            file_size=an.file_size or 0,
            mime_type="video/mp4",
        )
    if msg.video_note:
        return dict(
            file_id=msg.video_note.file_id, file_type="video_note",
            file_name="video_note.mp4",
            file_size=msg.video_note.file_size or 0,
            mime_type="video/mp4",
        )
    if msg.sticker:
        return dict(
            file_id=msg.sticker.file_id, file_type="sticker",
            file_name="sticker.webp",
            file_size=msg.sticker.file_size or 0,
            mime_type="image/webp",
        )
    return None
