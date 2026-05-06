"""
Reaction handler.

Handles react:<poster_id>:<key> callback queries.
Toggles the vote, rebuilds the keyboard, and edits the message in-place.
"""
from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from api.services.reaction_service import toggle_reaction, get_user_reaction
from api.keyboards.reactions import build_reaction_keyboard
from api.services.poster_service import get_poster
from api.utils.constants import REACTION_KEYS
from api.utils.logger import get_logger

router = Router(name="reactions")
logger = get_logger(__name__)


@router.callback_query(F.data.startswith("react:"))
async def cb_reaction(callback: CallbackQuery) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer("Invalid reaction.", show_alert=True)
        return

    _, poster_id, reaction_key = parts
    if reaction_key not in REACTION_KEYS:
        await callback.answer("Unknown reaction.", show_alert=True)
        return

    poster = await get_poster(poster_id)
    if not poster:
        await callback.answer("❌ Poster no longer exists.", show_alert=True)
        return

    user_id = callback.from_user.id
    try:
        counts, new_reaction = await toggle_reaction(poster_id, user_id, reaction_key)
    except Exception as exc:
        logger.error("Reaction toggle failed: %s", exc)
        await callback.answer("Error processing reaction.", show_alert=True)
        return

    kb = build_reaction_keyboard(poster_id, counts, new_reaction)
    try:
        await callback.message.edit_reply_markup(reply_markup=kb)
    except TelegramBadRequest:
        pass   # message unchanged — no-op

    feedback = (
        f"You reacted with {reaction_key} ✅"
        if new_reaction else
        "Reaction removed"
    )
    await callback.answer(feedback)
