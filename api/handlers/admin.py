"""
Admin dashboard handler — /admin command.

Everything gated behind settings.ADMIN_ID.

Features:
  • Overview stats
  • Paginated share list with inspect/delete
  • Paginated user list with ban/unban
  • Global analytics
  • Broadcast message
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from api.config import settings
from api.redis_client import get_redis
from api.services.analytics_service import get_global_stats
from api.services.share_service import get_user_shares, admin_delete_share, get_share
from api.services.security import ban_user, unban_user, get_all_user_ids, get_user_profile, is_admin
from api.services.pagination import paginate
from api.keyboards.admin import build_admin_main, build_admin_share_actions, build_admin_user_actions
from api.keyboards.pagination import build_pagination
from api.utils.constants import K_SHARES_SET, K_BANNED, ITEMS_PER_PAGE
from api.utils.helpers import fmt_ts, jloads
from api.utils.logger import get_logger

router = Router(name="admin")
logger = get_logger(__name__)


def _require_admin(user_id: int) -> bool:
    return user_id == settings.ADMIN_ID


# ── /admin ────────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not _require_admin(message.from_user.id):
        await message.answer("🚫 Admin only.")
        return
    await _send_dashboard(message)


async def _send_dashboard(message: Message) -> None:
    stats = await get_global_stats()
    text  = (
        "🛠 <b>Admin Dashboard</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Users:          <b>{stats['total_users']}</b>\n"
        f"🔗 Active Shares:  <b>{stats['active_shares']}</b>\n"
        f"⬇️  Downloads:      <b>{stats['total_downloads']}</b>\n"
        f"📢 Posters:        <b>{stats['poster_publishes']}</b>\n"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=build_admin_main())


# ── Refresh ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_refresh")
async def cb_refresh(callback: CallbackQuery) -> None:
    if not _require_admin(callback.from_user.id):
        await callback.answer("Admin only.", show_alert=True)
        return
    stats = await get_global_stats()
    text  = (
        "🛠 <b>Admin Dashboard</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Users:          <b>{stats['total_users']}</b>\n"
        f"🔗 Active Shares:  <b>{stats['active_shares']}</b>\n"
        f"⬇️  Downloads:      <b>{stats['total_downloads']}</b>\n"
        f"📢 Posters:        <b>{stats['poster_publishes']}</b>\n"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=build_admin_main())
    await callback.answer("Refreshed ✅")


# ── Shares list ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_shares:"))
async def cb_admin_shares(callback: CallbackQuery) -> None:
    if not _require_admin(callback.from_user.id):
        await callback.answer("Admin only.", show_alert=True)
        return

    page  = int(callback.data.split(":")[1])
    redis = await get_redis()
    all_ids = list(await redis.smembers(K_SHARES_SET()))
    paged   = paginate(all_ids, page)

    lines = [f"🗂 <b>All Shares</b> (page {paged['page']}/{paged['total_pages']})\n"]
    for sid in paged["items"]:
        share = await get_share(sid)
        dl    = share.get("downloads", 0) if share else "?"
        kind  = "📦" if share and share.get("type") == "multi" else "📄"
        lines.append(f"{kind} <code>{sid}</code>  ↓{dl}")

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = __import__("aiogram").utils.keyboard.InlineKeyboardBuilder()
    for sid in paged["items"]:
        builder.button(text=f"🔍 {sid}", callback_data=f"admin_inspect:{sid}")
    builder.adjust(1)

    nav = []
    if paged["has_prev"]:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin_shares:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{paged['page']}/{paged['total_pages']}", callback_data="noop"))
    if paged["has_next"]:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"admin_shares:{page+1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="⬅️ Dashboard", callback_data="admin_refresh"))

    await callback.message.edit_text(
        "\n".join(lines), parse_mode="HTML", reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_inspect:"))
async def cb_admin_inspect(callback: CallbackQuery) -> None:
    if not _require_admin(callback.from_user.id):
        await callback.answer("Admin only.", show_alert=True)
        return
    share_id = callback.data.split(":", 1)[1]
    share    = await get_share(share_id)
    if not share:
        await callback.answer("Share not found.", show_alert=True)
        return

    text = (
        f"🔍 <b>Share: <code>{share_id}</code></b>\n\n"
        f"👤 Owner: <code>{share.get('owner_id')}</code>\n"
        f"📦 Files: {len(share.get('files', []))}\n"
        f"⬇️  Downloads: {share.get('downloads', 0)}\n"
        f"📅 Created: {fmt_ts(share.get('created_at', 0))}\n"
        f"🏷 Type: {share.get('type', 'single')}\n"
    )
    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=build_admin_share_actions(share_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_del:"))
async def cb_admin_del(callback: CallbackQuery) -> None:
    if not _require_admin(callback.from_user.id):
        await callback.answer("Admin only.", show_alert=True)
        return
    share_id = callback.data.split(":", 1)[1]
    deleted  = await admin_delete_share(share_id)
    await callback.answer(f"{'Deleted ✅' if deleted else 'Not found ❌'}", show_alert=True)
    if deleted:
        await callback.message.edit_text(f"🗑 Share <code>{share_id}</code> deleted.", parse_mode="HTML")


# ── Analytics ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_analytics")
async def cb_admin_analytics(callback: CallbackQuery) -> None:
    if not _require_admin(callback.from_user.id):
        await callback.answer("Admin only.", show_alert=True)
        return
    stats = await get_global_stats()
    text  = (
        "📈 <b>Full Analytics</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 Total Users:         <b>{stats['total_users']}</b>\n"
        f"🔗 Active Shares:       <b>{stats['active_shares']}</b>\n"
        f"📤 Total Shares:        <b>{stats['total_shares']}</b>\n"
        f"📦 Multi Shares:        <b>{stats['total_multi']}</b>\n"
        f"⬇️  Total Downloads:     <b>{stats['total_downloads']}</b>\n"
        f"📁 Files Served:        <b>{stats['files_served']}</b>\n"
        f"📢 Poster Publishes:    <b>{stats['poster_publishes']}</b>\n"
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = __import__("aiogram").utils.keyboard.InlineKeyboardBuilder()
    builder.button(text="⬅️ Dashboard", callback_data="admin_refresh")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=builder.as_markup())
    await callback.answer()


# ── Users list ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_users:"))
async def cb_admin_users(callback: CallbackQuery) -> None:
    if not _require_admin(callback.from_user.id):
        await callback.answer("Admin only.", show_alert=True)
        return

    page     = int(callback.data.split(":")[1])
    all_ids  = await get_all_user_ids()
    paged    = paginate(all_ids, page)
    redis    = await get_redis()
    banned   = await redis.smembers(K_BANNED())

    lines = [f"👥 <b>Users</b> (page {paged['page']}/{paged['total_pages']})\n"]
    for uid in paged["items"]:
        profile  = await get_user_profile(uid)
        name     = profile.get("first_name", "?") if profile else "?"
        is_ban   = str(uid) in banned
        flag     = " 🚫" if is_ban else ""
        lines.append(f"• <code>{uid}</code>  {name}{flag}")

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    builder = __import__("aiogram").utils.keyboard.InlineKeyboardBuilder()
    for uid in paged["items"]:
        builder.button(text=f"👤 {uid}", callback_data=f"admin_view_user:{uid}")
    builder.adjust(1)

    nav = []
    if paged["has_prev"]:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin_users:{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{paged['page']}/{paged['total_pages']}", callback_data="noop"))
    if paged["has_next"]:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"admin_users:{page+1}"))
    if nav:
        builder.row(*nav)
    builder.row(InlineKeyboardButton(text="⬅️ Dashboard", callback_data="admin_refresh"))

    await callback.message.edit_text(
        "\n".join(lines), parse_mode="HTML", reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_view_user:"))
async def cb_admin_view_user(callback: CallbackQuery) -> None:
    if not _require_admin(callback.from_user.id):
        await callback.answer("Admin only.", show_alert=True)
        return
    uid     = int(callback.data.split(":", 1)[1])
    profile = await get_user_profile(uid)
    text    = (
        f"👤 <b>User: <code>{uid}</code></b>\n\n"
        f"Name:     {profile.get('first_name', '?') if profile else '?'}\n"
        f"Username: @{profile.get('username', '?') if profile else '?'}\n"
        f"Joined:   {fmt_ts(profile.get('joined_at', 0)) if profile else '?'}\n"
        f"Shares:   {profile.get('shares', 0) if profile else '?'}\n"
    )
    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=build_admin_user_actions(uid),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_ban:"))
async def cb_admin_ban(callback: CallbackQuery) -> None:
    if not _require_admin(callback.from_user.id):
        await callback.answer("Admin only.", show_alert=True)
        return
    uid = int(callback.data.split(":", 1)[1])
    if uid == settings.ADMIN_ID:
        await callback.answer("Cannot ban yourself.", show_alert=True)
        return
    await ban_user(uid)
    await callback.answer(f"User {uid} banned 🚫", show_alert=True)


@router.callback_query(F.data.startswith("admin_unban:"))
async def cb_admin_unban(callback: CallbackQuery) -> None:
    if not _require_admin(callback.from_user.id):
        await callback.answer("Admin only.", show_alert=True)
        return
    uid = int(callback.data.split(":", 1)[1])
    await unban_user(uid)
    await callback.answer(f"User {uid} unbanned ✅", show_alert=True)


# ── /list (alias for admin share overview) ────────────────────────────────────

@router.message(Command("list"))
async def cmd_list(message: Message) -> None:
    if not _require_admin(message.from_user.id):
        await message.answer("🚫 Admin only.")
        return
    redis   = await get_redis()
    all_ids = list(await redis.smembers(K_SHARES_SET()))
    paged   = paginate(all_ids, 1)
    lines   = [f"🗂 <b>All Shares</b> ({len(all_ids)} total)\n"]
    for sid in paged["items"]:
        share = await get_share(sid)
        dl    = share.get("downloads", 0) if share else "?"
        lines.append(f"• <code>{sid}</code>  ↓{dl}")
    if paged["total_pages"] > 1:
        lines.append(f"\n<i>Showing page 1/{paged['total_pages']}</i>")
    await message.answer("\n".join(lines), parse_mode="HTML")
