"""
Keyboards for share-related messages.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from api.config import settings


def build_share_link_keyboard(share_id: str) -> InlineKeyboardMarkup:
    """Button that opens the share link directly in a new chat."""
    link = f"https://t.me/{settings.BOT_USERNAME}?start={share_id}"
    builder = InlineKeyboardBuilder()
    builder.button(text="🔗 Open Share Link", url=link)
    builder.button(text="🗑 Delete", callback_data=f"del_share:{share_id}")
    builder.adjust(1)
    return builder.as_markup()


def build_delete_confirm_keyboard(share_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Yes, delete", callback_data=f"confirm_del:{share_id}")
    builder.button(text="❌ Cancel",       callback_data="cancel")
    builder.adjust(2)
    return builder.as_markup()


def build_my_shares_keyboard(shares: list, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Paginated list of user's shares."""
    builder = InlineKeyboardBuilder()
    for s in shares:
        sid   = s["id"]
        label = f"{'📦' if s.get('type') == 'multi' else '📄'} {sid}"
        builder.button(text=label, callback_data=f"view_share:{sid}")
    builder.adjust(1)

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"my_page:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"my_page:{page+1}"))
    if nav:
        builder.row(*nav)

    return builder.as_markup()


def build_multi_done_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Done — Create Link", callback_data="multi_done")
    builder.button(text="❌ Cancel",              callback_data="multi_cancel")
    builder.adjust(1)
    return builder.as_markup()
