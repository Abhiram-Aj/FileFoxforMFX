"""
Generic pagination keyboard builder.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def build_pagination(
    callback_prefix: str,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    """
    Build ⬅️ Prev  [page/total]  Next ➡️ navigation row.

    callback_prefix: e.g. "admin_page" → "admin_page:2"
    """
    builder = InlineKeyboardBuilder()
    nav: list[InlineKeyboardButton] = []

    if page > 1:
        nav.append(InlineKeyboardButton(
            text="⬅️ Prev",
            callback_data=f"{callback_prefix}:{page - 1}",
        ))

    nav.append(InlineKeyboardButton(
        text=f"{page} / {total_pages}",
        callback_data="noop",
    ))

    if page < total_pages:
        nav.append(InlineKeyboardButton(
            text="Next ➡️",
            callback_data=f"{callback_prefix}:{page + 1}",
        ))

    builder.row(*nav)
    return builder.as_markup()
