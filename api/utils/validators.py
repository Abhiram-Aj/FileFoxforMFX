"""
Input validation helpers.  All functions are pure — no I/O.
"""
import re
from datetime import datetime, timezone
from typing import Optional, Tuple
from urllib.parse import urlparse


# ── URL ────────────────────────────────────────────────────────────────────

def validate_url(url: str) -> bool:
    """Accept http:// or https:// URLs with a non-empty host."""
    try:
        r = urlparse(url.strip())
        return r.scheme in ("http", "https") and bool(r.netloc)
    except Exception:
        return False


# ── Schedule datetime ──────────────────────────────────────────────────────

def parse_schedule_dt(raw: str) -> Tuple[bool, Optional[datetime]]:
    """
    Parse 'YYYY-MM-DD HH:MM' (UTC).
    Returns (True, dt) on success; (False, None) if invalid or in the past.
    """
    try:
        dt = datetime.strptime(raw.strip(), "%Y-%m-%d %H:%M").replace(
            tzinfo=timezone.utc
        )
        if dt.timestamp() <= datetime.now(timezone.utc).timestamp():
            return False, None
        return True, dt
    except ValueError:
        return False, None


# ── ID format checks ───────────────────────────────────────────────────────

_SHARE_RE  = re.compile(r"^[sm]_[A-Za-z0-9]{8}$")
_POSTER_RE = re.compile(r"^p_[A-Za-z0-9]{8}$")
_SCH_RE    = re.compile(r"^sch_[A-Za-z0-9]{8}$")


def is_valid_share_id(v: str)    -> bool: return bool(_SHARE_RE.match(v))
def is_valid_poster_id(v: str)   -> bool: return bool(_POSTER_RE.match(v))
def is_valid_schedule_id(v: str) -> bool: return bool(_SCH_RE.match(v))


# ── General ────────────────────────────────────────────────────────────────

def sanitize(text: str, max_len: int = 1024) -> str:
    return text.strip()[:max_len] if text else ""


def validate_callback(data: Optional[str], prefix: str) -> bool:
    return (
        isinstance(data, str)
        and data.startswith(prefix)
        and len(data) < 200
        and "\x00" not in data
    )
