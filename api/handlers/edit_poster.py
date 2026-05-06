"""
/editposter <poster_id> handler.

FSM flow:
  PosterEdit.choose_field   → show edit menu
  PosterEdit.editing_caption → accept new caption text
  PosterEdit.editing_photo   → accept new photo
  PosterEdit.editing_button  → rebuild buttons
  PosterEdit.confirm         → save or discard
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from api.services.poster_service import get_poster, update_poster
from api.keyboards.poster import (
    build_poster_edit_menu,
    build_poster_create_confirm,
    build_add_button_keyboard,
    build_cancel_keyboard,
)
from api.states.poster_states import PosterEdit
from api.utils.constants import MAX_POSTER_BUTTONS
from api.utils.validators import sanitize, validate_url, is_valid_poster_id
from api.utils.logger import get_logger

router = Router(name="edit_poster")
logger = get_logger(__name__)


@router.message(Command("editposter"))
async def cmd_editposter(message: Message, state: FSMContext) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Usage: /editposter <poster_id>")
        return

    poster_id = parts[1].strip()
    if not is_valid_poster_id(poster_id):
        await message.answer("❌ Invalid poster ID.")
        return

    poster = await get_poster(poster_id)
    if not poster:
        await message.answer("❌ Poster not found.")
        return
    if poster["owner_id"] != message.from_user.id:
        await message.answer("❌ Not authorised.")
        return

    await state.set_state(PosterEdit.choose_field)
    await state.update_data(poster_id=poster_id, temp_buttons=poster.get("buttons", []))
    await message.answer(
        f"✏️ <b>Editing poster</b> <code>{poster_id}</code>\n\nChoose what to edit:",
        parse_mode="HTML",
        reply_markup=build_poster_edit_menu(poster_id),
    )


# ── Also accessible from callback (e.g. poster preview screen) ──────────────

@router.callback_query(F.data.startswith("edit_poster:"))
async def cb_edit_poster(callback: CallbackQuery, state: FSMContext) -> None:
    poster_id = callback.data.split(":", 1)[1]
    poster    = await get_poster(poster_id)
    if not poster or poster["owner_id"] != callback.from_user.id:
        await callback.answer("Not authorised.", show_alert=True)
        return
    await state.set_state(PosterEdit.choose_field)
    await state.update_data(poster_id=poster_id, temp_buttons=poster.get("buttons", []))
    await callback.message.edit_text(
        f"✏️ <b>Editing poster</b> <code>{poster_id}</code>\n\nChoose what to edit:",
        parse_mode="HTML",
        reply_markup=build_poster_edit_menu(poster_id),
    )
    await callback.answer()


# ── Edit Caption ─────────────────────────────────────────────────────────────

@router.callback_query(PosterEdit.choose_field, F.data.startswith("pe_caption:"))
async def cb_pe_caption(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PosterEdit.editing_caption)
    await callback.message.answer(
        "✍️ Send the <b>new caption</b> (or /skip to clear it):", parse_mode="HTML"
    )
    await callback.answer()


@router.message(PosterEdit.editing_caption, F.text)
async def got_new_caption(message: Message, state: FSMContext) -> None:
    text = "" if (message.text or "").strip() == "/skip" else sanitize(message.text or "", 1024)
    data = await state.get_data()
    await update_poster(data["poster_id"], {"caption": text})
    await state.set_state(PosterEdit.choose_field)
    await message.answer(
        "✅ Caption updated.",
        reply_markup=build_poster_edit_menu(data["poster_id"]),
    )


# ── Edit Photo ───────────────────────────────────────────────────────────────

@router.callback_query(PosterEdit.choose_field, F.data.startswith("pe_photo:"))
async def cb_pe_photo(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PosterEdit.editing_photo)
    await callback.message.answer("🖼 Send the <b>new photo</b>:", parse_mode="HTML")
    await callback.answer()


@router.message(PosterEdit.editing_photo, F.photo)
async def got_new_photo(message: Message, state: FSMContext) -> None:
    fid  = message.photo[-1].file_id
    data = await state.get_data()
    await update_poster(data["poster_id"], {"photo_file_id": fid})
    await state.set_state(PosterEdit.choose_field)
    await message.answer(
        "✅ Image updated.",
        reply_markup=build_poster_edit_menu(data["poster_id"]),
    )


# ── Edit Buttons ─────────────────────────────────────────────────────────────

@router.callback_query(PosterEdit.choose_field, F.data.startswith("pe_buttons:"))
async def cb_pe_buttons(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PosterEdit.editing_button)
    await state.update_data(temp_buttons=[])   # reset buttons
    await callback.message.answer(
        "🔘 Send buttons (one per message):\n"
        "<code>Label | https://url.com</code>  or  <code>Label</code>\n\n"
        "Press ✅ Done when finished.",
        parse_mode="HTML",
        reply_markup=build_add_button_keyboard(),
    )
    await callback.answer()


@router.message(PosterEdit.editing_button, F.text)
async def got_edit_button(message: Message, state: FSMContext) -> None:
    data    = await state.get_data()
    buttons = data.get("temp_buttons", [])
    if len(buttons) >= MAX_POSTER_BUTTONS:
        await message.answer(f"❌ Max {MAX_POSTER_BUTTONS} buttons.")
        return

    raw = (message.text or "").strip()
    if "|" in raw:
        parts = raw.split("|", 1)
        value = parts[1].strip()
        btn   = {"text": sanitize(parts[0], 64),
                 "type": "url" if validate_url(value) else "callback",
                 "value": value}
    else:
        btn = {"text": sanitize(raw, 64), "type": "callback", "value": "noop"}

    buttons.append(btn)
    await state.update_data(temp_buttons=buttons)
    await message.answer(
        f"✅ Button added ({len(buttons)}/{MAX_POSTER_BUTTONS})",
        reply_markup=build_add_button_keyboard(),
    )


@router.callback_query(PosterEdit.editing_button, F.data == "poster_btn_done")
async def cb_edit_btn_done(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await update_poster(data["poster_id"], {"buttons": data.get("temp_buttons", [])})
    await state.set_state(PosterEdit.choose_field)
    await callback.message.answer(
        "✅ Buttons updated.",
        reply_markup=build_poster_edit_menu(data["poster_id"]),
    )
    await callback.answer()


# ── Preview ───────────────────────────────────────────────────────────────────

@router.callback_query(PosterEdit.choose_field, F.data.startswith("pe_preview:"))
async def cb_pe_preview(callback: CallbackQuery, state: FSMContext) -> None:
    data      = await state.get_data()
    poster_id = data["poster_id"]
    poster    = await get_poster(poster_id)
    if not poster:
        await callback.answer("Poster not found.", show_alert=True)
        return
    await callback.message.bot.send_photo(
        chat_id=callback.message.chat.id,
        photo=poster["photo_file_id"],
        caption=f"👁 <b>Preview</b>\n\n{poster.get('caption', '')}",
        parse_mode="HTML",
    )
    await callback.answer("Preview sent ↑")


# ── Save & close ──────────────────────────────────────────────────────────────

@router.callback_query(PosterEdit.choose_field, F.data.startswith("pe_save:"))
async def cb_pe_save(callback: CallbackQuery, state: FSMContext) -> None:
    data      = await state.get_data()
    poster_id = data["poster_id"]
    await state.clear()
    await callback.message.edit_text(
        f"💾 Poster <code>{poster_id}</code> saved!",
        parse_mode="HTML",
        reply_markup=build_poster_create_confirm(poster_id),
    )
    await callback.answer("Saved ✅")
