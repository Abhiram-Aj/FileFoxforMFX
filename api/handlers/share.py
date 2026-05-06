"""
Single-file share handler.

Any message containing a supported file (when NOT in a multi session)
is auto-captured and a permanent share link is generated.
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from api.config import settings
from api.services import share_service
from api.keyboards.share import (
    build_share_link_keyboard,
    build_delete_confirm_keyboard,
    build_my_shares_keyboard,
)
from api.utils.helpers import extract_file, fmt_ts, fmt_size
from api.utils.logger import get_logger
from api.utils.validators import is_valid_share_id

router = Router(name="share")
logger = get_logger(__name__)


# ── File capture ────────────────────────────────────────────────────────────

@router.message(
    F.document | F.video | F.photo | F.audio |
    F.voice | F.animation | F.video_note | F.sticker,
)
async def handle_file(message: Message, state: FSMContext) -> None:
    # If user is in a multi-session, delegate to multi handler
    current = await state.get_state()
    if current and "MultiCollect" in current:
        return   # multi handler will pick it up via its own filter

    file_info = extract_file(message)
    if not file_info:
        return

    user_id  = message.from_user.id
    caption  = message.caption or ""

    share_id = await share_service.create_share(user_id, file_info, caption)
    link     = f"https://t.me/{settings.BOT_USERNAME}?start={share_id}"

    await message.answer(
        f"✅ <b>Share link created!</b>\n\n"
        f"📄 <b>File:</b> {file_info['file_name']}\n"
        f"📦 <b>Size:</b> {fmt_size(file_info['file_size'])}\n"
        f"🔗 <b>Link:</b> <code>{link}</code>\n\n"
        f"<i>Share ID: <code>{share_id}</code></i>",
        parse_mode="HTML",
        reply_markup=build_share_link_keyboard(share_id),
    )
    logger.info("User %s created share %s", user_id, share_id)


# ── /my — paginated share list ─────────────────────────────────────────────

@router.message(Command("my"))
async def cmd_my(message: Message) -> None:
    user_id = message.from_user.id
    result  = await share_service.get_user_shares(user_id, page=1)
    if not result["items"]:
        await message.answer("📭 You have no shares yet.\nSend any file to create one!")
        return
    await message.answer(
        _format_share_list(result),
        parse_mode="HTML",
        reply_markup=build_my_shares_keyboard(
            result["items"], result["page"], result["total_pages"]
        ),
    )


@router.callback_query(F.data.startswith("my_page:"))
async def cb_my_page(callback: CallbackQuery) -> None:
    page    = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    result  = await share_service.get_user_shares(user_id, page=page)
    await callback.message.edit_text(
        _format_share_list(result),
        parse_mode="HTML",
        reply_markup=build_my_shares_keyboard(
            result["items"], result["page"], result["total_pages"]
        ),
    )
    await callback.answer()


def _format_share_list(result: dict) -> str:
    lines = [f"📋 <b>Your Shares</b>  (page {result['page']}/{result['total_pages']})\n"]
    for i, s in enumerate(result["items"], 1):
        kind = "📦 Multi" if s.get("type") == "multi" else "📄 Single"
        dl   = s.get("downloads", 0)
        lines.append(f"{i}. <code>{s['id']}</code>  {kind}  ↓{dl}")
    return "\n".join(lines)


# ── View / delete share ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("view_share:"))
async def cb_view_share(callback: CallbackQuery) -> None:
    share_id = callback.data.split(":", 1)[1]
    share    = await share_service.get_share(share_id)
    if not share:
        await callback.answer("Share not found.", show_alert=True)
        return
    link = f"https://t.me/{settings.BOT_USERNAME}?start={share_id}"
    text = (
        f"📄 <b>Share Details</b>\n\n"
        f"🆔 <code>{share_id}</code>\n"
        f"📦 Files: {len(share['files'])}\n"
        f"↓ Downloads: {share.get('downloads', 0)}\n"
        f"📅 Created: {fmt_ts(share['created_at'])}\n"
        f"🔗 <code>{link}</code>"
    )
    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=build_share_link_keyboard(share_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("del_share:"))
async def cb_del_share(callback: CallbackQuery) -> None:
    share_id = callback.data.split(":", 1)[1]
    share    = await share_service.get_share(share_id)
    if not share or share["owner_id"] != callback.from_user.id:
        await callback.answer("Not authorised.", show_alert=True)
        return
    await callback.message.edit_text(
        f"🗑 Delete share <code>{share_id}</code>?",
        parse_mode="HTML",
        reply_markup=build_delete_confirm_keyboard(share_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del:"))
async def cb_confirm_del(callback: CallbackQuery) -> None:
    share_id = callback.data.split(":", 1)[1]
    deleted  = await share_service.delete_share(share_id, callback.from_user.id)
    if deleted:
        await callback.message.edit_text(f"✅ Share <code>{share_id}</code> deleted.", parse_mode="HTML")
    else:
        await callback.answer("Could not delete.", show_alert=True)
    await callback.answer()


# ── /find — search by share_id ──────────────────────────────────────────────

@router.message(Command("find"))
async def cmd_find(message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /find <share_id>")
        return
    sid   = parts[1].strip()
    if not is_valid_share_id(sid):
        await message.answer("❌ Invalid share ID format.")
        return
    share = await share_service.get_share(sid)
    if not share:
        await message.answer("❌ Share not found.")
        return
    link = f"https://t.me/{settings.BOT_USERNAME}?start={sid}"
    await message.answer(
        f"🔍 <b>Share found</b>\n\n"
        f"🆔 <code>{sid}</code>\n"
        f"📦 Files: {len(share['files'])}\n"
        f"↓ Downloads: {share.get('downloads', 0)}\n"
        f"🔗 <code>{link}</code>",
        parse_mode="HTML",
        reply_markup=build_share_link_keyboard(sid),
    )


# ── /delete <share_id> ──────────────────────────────────────────────────────

@router.message(Command("delete"))
async def cmd_delete(message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /delete <share_id>")
        return
    sid     = parts[1].strip()
    deleted = await share_service.delete_share(sid, message.from_user.id)
    if deleted:
        await message.answer(f"✅ Share <code>{sid}</code> deleted.", parse_mode="HTML")
    else:
        await message.answer("❌ Share not found or you don't own it.")


# ── noop callback ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def cb_cancel(callback: CallbackQuery) -> None:
    await callback.message.delete()
    await callback.answer("Cancelled.")
