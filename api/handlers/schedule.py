"""
Schedule handler.

Commands:
  /schedule <poster_id> YYYY-MM-DD HH:MM  → inline command
  /schedule <poster_id>                    → FSM flow for datetime

Also handles the callback shortcut from the poster preview screen.
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from api.config import settings
from api.services.scheduler import create_schedule
from api.services.poster_service import get_poster
from api.services.security import is_admin
from api.states.poster_states import ScheduleCreate
from api.utils.helpers import fmt_ts
from api.utils.validators import parse_schedule_dt, is_valid_poster_id
from api.utils.logger import get_logger

router = Router(name="schedule")
logger = get_logger(__name__)


@router.message(Command("schedule"))
async def cmd_schedule(message: Message, state: FSMContext) -> None:
    parts = (message.text or "").split(maxsplit=2)

    # Validate poster_id
    if len(parts) < 2:
        await message.answer(
            "Usage:\n"
            "<code>/schedule &lt;poster_id&gt; YYYY-MM-DD HH:MM</code>\n"
            "or\n"
            "<code>/schedule &lt;poster_id&gt;</code>  (guided mode)",
            parse_mode="HTML",
        )
        return

    poster_id = parts[1].strip()
    if not is_valid_poster_id(poster_id):
        await message.answer("❌ Invalid poster ID format.")
        return

    poster = await get_poster(poster_id)
    if not poster:
        await message.answer("❌ Poster not found.")
        return
    if poster["owner_id"] != message.from_user.id and not is_admin(message.from_user.id):
        await message.answer("❌ Not authorised.")
        return

    # Inline mode: datetime provided directly
    if len(parts) == 3:
        dt_str = parts[2].strip()
        await _do_schedule(message, poster_id, dt_str)
        return

    # FSM mode
    await state.set_state(ScheduleCreate.waiting_datetime)
    await state.update_data(poster_id=poster_id)
    await message.answer(
        f"⏰ Scheduling poster <code>{poster_id}</code>\n\n"
        "Send the publish date/time in UTC:\n"
        "<code>YYYY-MM-DD HH:MM</code>\n\n"
        "Example: <code>2026-06-15 14:30</code>",
        parse_mode="HTML",
    )


@router.message(ScheduleCreate.waiting_datetime, F.text)
async def got_schedule_dt(message: Message, state: FSMContext) -> None:
    data      = await state.get_data()
    poster_id = data.get("poster_id", "")
    await state.clear()
    await _do_schedule(message, poster_id, (message.text or "").strip())


async def _do_schedule(message: Message, poster_id: str, dt_str: str) -> None:
    ok, dt = parse_schedule_dt(dt_str)
    if not ok or dt is None:
        await message.answer(
            "❌ Invalid or past datetime.\n"
            "Format: <code>YYYY-MM-DD HH:MM</code> (UTC)",
            parse_mode="HTML",
        )
        return

    channel_id = settings.DEFAULT_CHANNEL_ID
    if not channel_id:
        await message.answer("⚠️ No default channel configured. Set DEFAULT_CHANNEL_ID.")
        return

    sched_id = await create_schedule(
        poster_id=poster_id,
        publish_at_str=dt_str,
        channel_id=channel_id,
        owner_id=message.from_user.id,
    )

    if not sched_id:
        await message.answer("❌ Failed to create schedule.")
        return

    await message.answer(
        f"✅ <b>Scheduled!</b>\n\n"
        f"📌 Poster: <code>{poster_id}</code>\n"
        f"📅 Publishes at: <b>{fmt_ts(int(dt.timestamp()))}</b>\n"
        f"🆔 Schedule ID: <code>{sched_id}</code>",
        parse_mode="HTML",
    )
    logger.info("Scheduled poster %s at %s (sched=%s)", poster_id, dt, sched_id)


# ── Shortcut from poster preview keyboard ────────────────────────────────────

@router.callback_query(F.data.startswith("sched_poster:"))
async def cb_sched_poster(callback: CallbackQuery, state: FSMContext) -> None:
    poster_id = callback.data.split(":", 1)[1]
    poster    = await get_poster(poster_id)
    if not poster or poster["owner_id"] != callback.from_user.id:
        await callback.answer("Not authorised.", show_alert=True)
        return
    await state.set_state(ScheduleCreate.waiting_datetime)
    await state.update_data(poster_id=poster_id)
    await callback.message.answer(
        f"⏰ Send the UTC publish datetime for <code>{poster_id}</code>:\n"
        "<code>YYYY-MM-DD HH:MM</code>",
        parse_mode="HTML",
    )
    await callback.answer()
