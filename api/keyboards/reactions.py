"""
Reaction keyboard builder.

The keyboard is rebuilt on every callback to show live counts.
"""
from typing import Dict, Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from api.utils.constants import REACTION_KEYS, REACTION_EMOJI


def build_reaction_keyboard(
    poster_id: str,
    counts: Dict[str, int],
    user_reaction: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """
    Build a row of reaction buttons with live counts.
    The active reaction is marked with a dot prefix to give visual feedback.
    """
    builder = InlineKeyboardBuilder()
    for key in REACTION_KEYS:
        emoji  = REACTION_EMOJI[key]
        count  = counts.get(key, 0)
        active = "·" if user_reaction == key else ""
        label  = f"{active}{emoji} {count}"
        builder.button(text=label, callback_data=f"react:{poster_id}:{key}")
    builder.adjust(3)
    return builder.as_markup()
