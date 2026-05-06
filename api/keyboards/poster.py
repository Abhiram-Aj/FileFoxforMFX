"""
Keyboards for the poster creation and editing flows.
"""
from typing import Dict, List, Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from api.utils.validators import validate_url


def build_poster_buttons(buttons: List[Dict]) -> InlineKeyboardMarkup:
    """
    Render the poster's own inline buttons as defined by the creator.
    Button dict format:  {"text": "...", "type": "url|callback", "value": "..."}
    """
    builder = InlineKeyboardBuilder()
    for btn in buttons:
        if btn.get("type") == "url" and validate_url(btn.get("value", "")):
            builder.button(text=btn["text"], url=btn["value"])
        else:
            builder.button(
                text=btn["text"],
                callback_data=f"poster_btn:{btn.get('value', 'noop')}",
            )
    builder.adjust(1)
    return builder.as_markup()


def build_poster_create_confirm(poster_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Publish Now",    callback_data=f"publish_poster:{poster_id}")
    builder.button(text="⏰ Schedule",       callback_data=f"sched_poster:{poster_id}")
    builder.button(text="✏️ Edit",           callback_data=f"edit_poster:{poster_id}")
    builder.button(text="🗑 Delete",         callback_data=f"del_poster:{poster_id}")
    builder.adjust(2)
    return builder.as_markup()


def build_poster_edit_menu(poster_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Edit Caption",  callback_data=f"pe_caption:{poster_id}")
    builder.button(text="🖼 Edit Image",    callback_data=f"pe_photo:{poster_id}")
    builder.button(text="🔘 Edit Buttons",  callback_data=f"pe_buttons:{poster_id}")
    builder.button(text="👁 Preview",       callback_data=f"pe_preview:{poster_id}")
    builder.button(text="💾 Save & Close",  callback_data=f"pe_save:{poster_id}")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def build_add_button_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Add Another Button", callback_data="poster_add_btn")
    builder.button(text="✅ Done",               callback_data="poster_btn_done")
    builder.adjust(1)
    return builder.as_markup()


def build_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Cancel", callback_data="cancel")
    return builder.as_markup()
