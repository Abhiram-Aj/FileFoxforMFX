"""
/start handler.

Dual role:
  1. Plain /start → welcome screen.
  2. /start <share_id>  → deliver shared files directly.
"""
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from api.config import settings
from api.services.media_sender import send_files
from api.services.share_service import get_share, increment_downloads
from api.utils.helpers import fmt_ts
from api.utils.logger import get_logger
from api.utils.validators import is_valid_share_id

router = Router(name="start")
logger = get_logger(__name__)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    args = (message.text or "").split(maxsplit=1)
    payload = args[1].strip() if len(args) > 1 else ""

    # ── Deep-link: deliver a share ─────────────────────────────────────────
    if payload and is_valid_share_id(payload):
        share = await get_share(payload)
        if not share:
            await message.answer("❌ Share not found or has been deleted.")
            return

        try:
            await send_files(
                bot=message.bot,
                chat_id=message.chat.id,
                files=share["files"],
                caption=share.get("caption", ""),
            )
            await increment_downloads(payload)
        except Exception as exc:
            logger.error("Failed to deliver share %s: %s", payload, exc)
            await message.answer("⚠️ Could not deliver the file. Please try again later.")
        return

    # ── Plain /start → welcome ─────────────────────────────────────────────
    name = message.from_user.first_name or "there"
    await message.answer(
        f"👋 Hey <b>{name}</b>! Welcome to <b>ShareBot</b>.\n\n"
        "📁 Send me <b>any file</b> to get a permanent share link.\n\n"
        "<b>Commands:</b>\n"
        "/multi — create a multi-file share\n"
        "/poster — create a poster\n"
        "/my — your shares\n"
        "/stats — analytics\n"
        "/help — full command list",
        parse_mode="HTML",
    )
