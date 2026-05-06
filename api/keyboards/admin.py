"""
Admin dashboard keyboards.
"""
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def build_admin_main() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🗂 All Shares",    callback_data="admin_shares:1")
    builder.button(text="📈 Analytics",    callback_data="admin_analytics")
    builder.button(text="👥 Users",        callback_data="admin_users:1")
    builder.button(text="🔄 Refresh",      callback_data="admin_refresh")
    builder.adjust(2, 2)
    return builder.as_markup()


def build_admin_share_actions(share_id: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 Inspect",  callback_data=f"admin_inspect:{share_id}")
    builder.button(text="🗑 Delete",   callback_data=f"admin_del:{share_id}")
    builder.button(text="⬅️ Back",     callback_data="admin_shares:1")
    builder.adjust(2, 1)
    return builder.as_markup()


def build_admin_user_actions(user_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Ban",     callback_data=f"admin_ban:{user_id}")
    builder.button(text="✅ Unban",   callback_data=f"admin_unban:{user_id}")
    builder.button(text="⬅️ Back",    callback_data="admin_users:1")
    builder.adjust(2, 1)
    return builder.as_markup()
