"""
/poster handler — guided FSM flow to build a poster template.

Flow:
  PosterCreate.waiting_photo   → user sends a photo
  PosterCreate.waiting_caption → user types caption (or skips)
  PosterCreate.waiting_button  → user adds buttons (loop, up to MAX_POSTER_BUTTONS)
  PosterCreate.confirm         → preview + action keyboard
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from api.services.poster_service import create_poster, get_poster, delete_poster
from api.services.reaction_service import get_counts
from api.keyboards.poster import (
    build_poster_buttons,
    build_poster_create_confirm,
    build_add_button_keyboard,
    build_cancel_keyboard,
)
from api.keyboards.reactions import build_reaction_keyboard
from api.states.poster_states import PosterCreate
from api.utils.constants import MAX_POSTER_BUTTONS
from api.utils.validators import sanitize, validate_url
from api.utils.logger import get_logger

router = Router(name="poster")
logger = get_logger(__name__)

_BTN_INSTRUCTIONS = (
    "🔘 <b>Add a button</b> (optional)\n\n"
    "Format:\n"
    "<code>Button Text | https://example.com</code>  (URL button)\n"
    "<code>Button Text</code>  (callback button)\n\n"
    f"Up to {MAX_POSTER_BUTTONS} buttons total."
)


# ── Entry ───────────────────────────────────────────────────────────────────

@router.message(Command("poster"))
async def cmd_poster(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(PosterCreate.waiting_photo)
    await message.answer(
        "🖼 <b>Poster Creator</b>\n\nSend the <b>poster image</b> to get started.",
        parse_mode="HTML",
        reply_markup=build_cancel_keyboard(),
    )


# ── Step 1: Photo ────────────────────────────────────────────────────────────

@router.message(PosterCreate.waiting_photo, F.photo)
async def got_photo(message: Message, state: FSMContext) -> None:
    photo_fid = message.photo[-1].file_id
    await state.update_data(photo_file_id=photo_fid, buttons=[])
    await state.set_state(PosterCreate.waiting_caption)
    await message.answer(
        "✍️ Now send the <b>poster caption</b> (supports HTML).\n"
        "Or type /skip to leave it empty.",
        parse_mode="HTML",
        reply_markup=build_cancel_keyboard(),
    )


@router.message(PosterCreate.waiting_photo)
async def photo_not_sent(message: Message) -> None:
    await message.answer("❌ Please send a <b>photo</b>.", parse_mode="HTML")


# ── Step 2: Caption ──────────────────────────────────────────────────────────

@router.message(PosterCreate.waiting_caption, Command("skip"))
@router.message(PosterCreate.waiting_caption, F.text)
async def got_caption(message: Message, state: FSMContext) -> None:
    caption = "" if (message.text or "").strip() == "/skip" else sanitize(message.text or "", 1024)
    await state.update_data(caption=caption)
    await state.set_state(PosterCreate.waiting_button)
    await message.answer(_BTN_INSTRUCTIONS, parse_mode="HTML", reply_markup=build_add_button_keyboard())


# ── Step 3: Buttons (loop) ───────────────────────────────────────────────────

@router.message(PosterCreate.waiting_button, F.text)
async def got_button(message: Message, state: FSMContext) -> None:
    data    = await state.get_data()
    buttons: list = data.get("buttons", [])

    if len(buttons) >= MAX_POSTER_BUTTONS:
        await message.answer(f"❌ Maximum {MAX_POSTER_BUTTONS} buttons reached.")
        await _go_to_confirm(message, state)
        return

    raw = (message.text or "").strip()
    if "|" in raw:
        parts = raw.split("|", 1)
        text  = sanitize(parts[0], 64)
        value = parts[1].strip()
        if validate_url(value):
            buttons.append({"text": text, "type": "url",      "value": value})
        else:
            buttons.append({"text": text, "type": "callback", "value": value})
    else:
        buttons.append({"text": sanitize(raw, 64), "type": "callback", "value": "noop"})

    await state.update_data(buttons=buttons)
    remaining = MAX_POSTER_BUTTONS - len(buttons)
    await message.answer(
        f"✅ Button added! ({len(buttons)}/{MAX_POSTER_BUTTONS})\n"
        f"Send another or press ✅ Done.",
        reply_markup=build_add_button_keyboard() if remaining > 0 else None,
    )


@router.callback_query(PosterCreate.waiting_button, F.data == "poster_add_btn")
async def cb_add_more(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.answer(_BTN_INSTRUCTIONS, parse_mode="HTML",
                                  reply_markup=build_add_button_keyboard())
    await callback.answer()


@router.callback_query(PosterCreate.waiting_button, F.data == "poster_btn_done")
async def cb_btn_done(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _go_to_confirm(callback.message, state)


# ── Step 4: Confirm ──────────────────────────────────────────────────────────

async def _go_to_confirm(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.set_state(PosterCreate.confirm)

    user_id   = message.chat.id
    poster_id = await create_poster(
        owner_id=user_id,
        photo_file_id=data["photo_file_id"],
        caption=data.get("caption", ""),
        buttons=data.get("buttons", []),
    )
    await state.update_data(poster_id=poster_id)

    kb = build_poster_create_confirm(poster_id)
    await message.bot.send_photo(
        chat_id=user_id,
        photo=data["photo_file_id"],
        caption=f"👁 <b>Preview</b>\n\n{data.get('caption', '')}\n\n"
                f"🆔 <code>{poster_id}</code>",
        parse_mode="HTML",
        reply_markup=kb,
    )


# ── Publish now ──────────────────────────────────────────────────────────────

@router.message(Command("publish"))
async def cmd_publish(message: Message) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /publish <poster_id>")
        return
    await _publish_poster(message, parts[1].strip(), message.from_user.id)


@router.callback_query(F.data.startswith("publish_poster:"))
async def cb_publish_poster(callback: CallbackQuery, state: FSMContext) -> None:
    poster_id = callback.data.split(":", 1)[1]
    await state.clear()
    await callback.answer()
    await _publish_poster(callback.message, poster_id, callback.from_user.id)


async def _publish_poster(message: Message, poster_id: str, user_id: int) -> None:
    from api.config import settings
    poster = await get_poster(poster_id)
    if not poster:
        await message.answer("❌ Poster not found.")
        return
    if poster["owner_id"] != user_id:
        await message.answer("❌ Not authorised.")
        return

    channel_id = settings.DEFAULT_CHANNEL_ID
    if not channel_id:
        await message.answer(
            "⚠️ No default channel configured.\n"
            "Use /schedule to set a target channel, or ask the admin to set DEFAULT_CHANNEL_ID."
        )
        return

    counts = await get_counts(poster_id)
    kb = build_reaction_keyboard(poster_id, counts)
    user_buttons = build_poster_buttons(poster.get("buttons", []))

    # Merge keyboards is tricky — for simplicity reactions take precedence
    final_kb = kb if not poster.get("buttons") else user_buttons

    try:
        sent = await message.bot.send_photo(
            chat_id=channel_id,
            photo=poster["photo_file_id"],
            caption=poster.get("caption", ""),
            parse_mode="HTML",
            reply_markup=kb,
        )
        from api.services.poster_service import mark_published
        await mark_published(poster_id, channel_id, sent.message_id)
        await message.answer(f"📢 Poster <code>{poster_id}</code> published!", parse_mode="HTML")
    except Exception as exc:
        logger.error("Publish failed: %s", exc)
        await message.answer("❌ Failed to publish. Check the channel ID and bot permissions.")


# ── Delete poster ────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("del_poster:"))
async def cb_del_poster(callback: CallbackQuery, state: FSMContext) -> None:
    poster_id = callback.data.split(":", 1)[1]
    deleted   = await delete_poster(poster_id, callback.from_user.id)
    await state.clear()
    if deleted:
        await callback.message.edit_text(f"🗑 Poster <code>{poster_id}</code> deleted.", parse_mode="HTML")
    else:
        await callback.answer("Could not delete.", show_alert=True)
    await callback.answer()
