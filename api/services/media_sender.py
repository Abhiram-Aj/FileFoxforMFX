"""
Media sender service.

Never touches file bytes — only file_ids.

Routing rules:
  • single photo / video in a media-group capable list → sendMediaGroup
  • sendMediaGroup can hold max 10 items → auto-chunk
  • everything else → send individually
"""
import asyncio
from typing import Dict, List, Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import (
    InputMediaAudio,
    InputMediaDocument,
    InputMediaPhoto,
    InputMediaVideo,
)

from api.utils.constants import MEDIA_GROUP_SIZE, MEDIA_GROUP_TYPES
from api.utils.helpers import chunk_list
from api.utils.logger import get_logger

logger = get_logger(__name__)


def _make_input_media(file: Dict, caption: str = "", is_first: bool = False):
    """Build the correct InputMedia* object for a file dict."""
    ftype   = file["file_type"]
    fid     = file["file_id"]
    cap     = caption if is_first else None

    if ftype == "photo":
        return InputMediaPhoto(media=fid, caption=cap, parse_mode="HTML" if cap else None)
    if ftype == "video":
        return InputMediaVideo(media=fid, caption=cap, parse_mode="HTML" if cap else None)
    if ftype == "audio":
        return InputMediaAudio(media=fid, caption=cap, parse_mode="HTML" if cap else None)
    # documents and everything else
    return InputMediaDocument(media=fid, caption=cap, parse_mode="HTML" if cap else None)


async def send_single_file(
    bot: Bot,
    chat_id: int,
    file: Dict,
    caption: str = "",
    reply_markup=None,
) -> None:
    """Send one file to a chat using the appropriate API method."""
    ftype = file["file_type"]
    fid   = file["file_id"]
    kw    = dict(caption=caption or None, parse_mode="HTML", reply_markup=reply_markup)

    try:
        if ftype == "photo":
            await bot.send_photo(chat_id, fid, **kw)
        elif ftype == "video":
            await bot.send_video(chat_id, fid, **kw)
        elif ftype == "document":
            await bot.send_document(chat_id, fid, **kw)
        elif ftype == "audio":
            await bot.send_audio(chat_id, fid, **kw)
        elif ftype == "voice":
            await bot.send_voice(chat_id, fid, **kw)
        elif ftype == "animation":
            await bot.send_animation(chat_id, fid, **kw)
        elif ftype == "video_note":
            await bot.send_video_note(chat_id, fid)
        elif ftype == "sticker":
            await bot.send_sticker(chat_id, fid)
        else:
            await bot.send_document(chat_id, fid, **kw)
    except TelegramBadRequest as exc:
        logger.error("send_single_file failed fid=%s: %s", fid, exc)
        raise


async def send_files(
    bot: Bot,
    chat_id: int,
    files: List[Dict],
    caption: str = "",
    reply_markup=None,
) -> None:
    """
    Intelligently send one or many files.

    Strategy:
      1. Single file → send_single_file.
      2. All files are photo/video → sendMediaGroup (chunked by 10).
      3. Mixed types → send sequentially, attach caption to first.
    """
    if not files:
        return

    if len(files) == 1:
        await send_single_file(bot, chat_id, files[0], caption, reply_markup)
        return

    # Check if all files are media-group compatible
    all_media = all(f["file_type"] in MEDIA_GROUP_TYPES for f in files)

    if all_media:
        chunks = chunk_list(files, MEDIA_GROUP_SIZE)
        for i, chunk in enumerate(chunks):
            media = [
                _make_input_media(f, caption if (i == 0 and j == 0) else "", j == 0 and i == 0)
                for j, f in enumerate(chunk)
            ]
            try:
                await bot.send_media_group(chat_id, media=media)
            except TelegramBadRequest as exc:
                logger.error("send_media_group chunk %d failed: %s", i, exc)
                # fallback: send individually
                for f in chunk:
                    await send_single_file(bot, chat_id, f)
            # Respect Telegram flood control between chunks
            if i < len(chunks) - 1:
                await asyncio.sleep(0.5)
    else:
        # Mixed / non-media types → sequential
        for i, file in enumerate(files):
            cap = caption if i == 0 else ""
            mkp = reply_markup if i == len(files) - 1 else None
            await send_single_file(bot, chat_id, file, cap, mkp)
            if i < len(files) - 1:
                await asyncio.sleep(0.3)
