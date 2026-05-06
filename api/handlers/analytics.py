"""
Analytics handler — /stats command.

Admin-only rich dashboard.  Regular users get a lightweight summary.
"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from api.config import settings
from api.services.analytics_service import get_global_stats
from api.utils.logger import get_logger

router = Router(name="analytics")
logger = get_logger(__name__)


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    user_id  = message.from_user.id
    is_admin = user_id == settings.ADMIN_ID
    stats    = await get_global_stats()

    if is_admin:
        text = (
            "📊 <b>BOT ANALYTICS</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👥 Total Users:         <b>{stats['total_users']}</b>\n"
            f"🔗 Active Shares:       <b>{stats['active_shares']}</b>\n"
            f"📤 Total Shares:        <b>{stats['total_shares']}</b>\n"
            f"📦 Multi Shares:        <b>{stats['total_multi']}</b>\n"
            f"⬇️  Downloads:           <b>{stats['total_downloads']}</b>\n"
            f"📁 Files Served:        <b>{stats['files_served']}</b>\n"
            f"📢 Poster Publishes:    <b>{stats['poster_publishes']}</b>\n"
        )
    else:
        text = (
            "📊 <b>Bot Stats</b>\n\n"
            f"🔗 Active Shares:  <b>{stats['active_shares']}</b>\n"
            f"⬇️  Downloads:      <b>{stats['total_downloads']}</b>\n"
            f"📢 Posters:        <b>{stats['poster_publishes']}</b>\n"
        )

    await message.answer(text, parse_mode="HTML")
