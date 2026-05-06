"""
/multi handler — collect up to 50 files, then mint a single share link.

Flow:
  1. /multi              → enter MultiCollect.collecting state
  2. Send files          → added to Redis session one by one
  3. ✅ Done button / /done → create multi share, exit state
  4. ❌ Cancel           → clear session, exit state
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from api.config import settings
from api.services import share_service
from api.keyboards.share import build_share_link_keyboard, build_multi_done_keyboard
from api.states.poster_states import MultiCollect
from api.utils.constants import MAX_MULTI_FILES
from api.utils.helpers import extract_file, fmt_size
from api.utils.logger import get_logger

router = Router(name="multi")
logger = get_logger(__name__)


@router.message(Command("multi"))
async def cmd_multi(message: Message, state: FSMContext) -> None:
    user_id = message.from_user.id
    await share_service.session_start(user_id)
    await state.set_state(MultiCollect.collecting)
    await message.answer(
        "📥 <b>Multi-File Share</b>\n\n"
        f"Send up to <b>{MAX_MULTI_FILES}</b> files one by one.\n"
        "Press <b>✅ Done</b> when finished, or type /done.\n"
        "Press <b>❌ Cancel</b> to abort.",
        parse_mode="HTML",
        reply_markup=build_multi_done_keyboard(),
    )


@router.message(
    MultiCollect.collecting,
    F.document | F.video | F.photo | F.audio |
    F.voice | F.animation | F.video_note | F.sticker,
)
async def collect_file(message: Message, state: FSMContext) -> None:
    user_id   = message.from_user.id
    file_info = extract_file(message)
    if not file_info:
        return

    count = await share_service.session_add_file(user_id, file_info)
    if count == -1:
        await message.answer(
            f"❌ Maximum {MAX_MULTI_FILES} files allowed.\n"
            "Press ✅ Done to create your share link.",
            reply_markup=build_multi_done_keyboard(),
        )
        return

    await message.answer(
        f"✅ Added: <b>{file_info['file_name']}</b> ({fmt_size(file_info['file_size'])})\n"
        f"📦 Total: <b>{count}</b> file(s)",
        parse_mode="HTML",
        reply_markup=build_multi_done_keyboard(),
    )


@router.message(MultiCollect.collecting, Command("done"))
async def cmd_done(message: Message, state: FSMContext) -> None:
    await _finalise(message, state, message.from_user.id)


@router.callback_query(MultiCollect.collecting, F.data == "multi_done")
async def cb_multi_done(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _finalise(callback.message, state, callback.from_user.id, edit=True)


@router.callback_query(MultiCollect.collecting, F.data == "multi_cancel")
async def cb_multi_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await share_service.session_clear(callback.from_user.id)
    await state.clear()
    await callback.message.edit_text("❌ Multi-share cancelled.")
    await callback.answer()


async def _finalise(
    message: Message,
    state: FSMContext,
    user_id: int,
    edit: bool = False,
) -> None:
    session = await share_service.session_get(user_id)
    if not session or not session.get("files"):
        txt = "❌ No files collected. Send at least one file."
        if edit:
            await message.edit_text(txt)
        else:
            await message.answer(txt)
        return

    files    = session["files"]
    share_id = await share_service.create_multi_share(user_id, files)
    link     = f"https://t.me/{settings.BOT_USERNAME}?start={share_id}"

    await share_service.session_clear(user_id)
    await state.clear()

    text = (
        f"✅ <b>Multi-Share Created!</b>\n\n"
        f"📦 <b>{len(files)} file(s)</b> bundled\n"
        f"🔗 <b>Link:</b> <code>{link}</code>\n\n"
        f"<i>ID: <code>{share_id}</code></i>"
    )
    kb = build_share_link_keyboard(share_id)
    if edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)

    logger.info("User %s created multi share %s (%d files)", user_id, share_id, len(files))
