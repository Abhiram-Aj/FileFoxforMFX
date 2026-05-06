"""
FastAPI entrypoint — the only file Vercel sees.

Routes:
  POST /webhook          → Telegram update handler
  GET  /cron             → scheduled publisher (call every minute via cron)
  GET  /health           → uptime check
  POST /set_webhook      → one-time webhook registration helper
"""
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import Update
from aiogram.webhook.aiohttp_server import SimpleRequestHandler   # not used, kept for reference
from fastapi import FastAPI, Request, Response, Header, HTTPException
from fastapi.responses import JSONResponse

from api.config import settings
from api.redis_client import get_redis, close_redis
from api.middleware.rate_limit import RateLimitMiddleware
from api.middleware.auth import AuthMiddleware

# ── Handlers ──────────────────────────────────────────────────────────────────
from api.handlers import (
    start, share, multi, poster, edit_poster,
    reactions, schedule, analytics, admin,
)

from api.services.scheduler import process_due_schedules
from api.utils.logger import get_logger

logger = get_logger(__name__)

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="Telegram Share Bot", docs_url=None, redoc_url=None)

# ── Bot + Dispatcher (module-level singletons for Vercel cold-start caching) ──
_bot: Bot | None = None
_dp:  Dispatcher | None = None


async def _get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
    return _bot


async def _get_dp() -> Dispatcher:
    global _dp
    if _dp is None:
        redis  = await get_redis()
        storage = RedisStorage(redis=redis)
        _dp    = Dispatcher(storage=storage)

        # ── Middleware (order matters — auth first, then rate limit) ──────────
        _dp.message.middleware(AuthMiddleware())
        _dp.callback_query.middleware(AuthMiddleware())
        _dp.message.middleware(RateLimitMiddleware())

        # ── Routers ───────────────────────────────────────────────────────────
        # Order: most specific first to avoid catch-all conflicts
        _dp.include_router(admin.router)
        _dp.include_router(analytics.router)
        _dp.include_router(schedule.router)
        _dp.include_router(edit_poster.router)
        _dp.include_router(poster.router)
        _dp.include_router(reactions.router)
        _dp.include_router(multi.router)
        _dp.include_router(share.router)   # file handler last — it's a catch-all
        _dp.include_router(start.router)

    return _dp


# ── Webhook endpoint ──────────────────────────────────────────────────────────

@app.post(settings.WEBHOOK_PATH)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> Response:
    # Validate the secret token Telegram sends with every update
    if x_telegram_bot_api_secret_token != settings.WEBHOOK_SECRET:
        logger.warning("Rejected webhook — bad secret token")
        raise HTTPException(status_code=403, detail="Forbidden")

    bot = await _get_bot()
    dp  = await _get_dp()

    try:
        body   = await request.json()
        update = Update.model_validate(body, context={"bot": bot})
        await dp.feed_update(bot=bot, update=update)
    except Exception as exc:
        logger.error("Webhook processing error: %s", exc, exc_info=True)
        # Always return 200 to Telegram so it doesn't retry
    return Response(status_code=200)


# ── Cron endpoint — call every minute from Vercel Cron / cron-job.org ────────

@app.get("/cron")
async def cron_tick(
    x_cron_secret: str | None = Header(default=None),
) -> JSONResponse:
    # Optional: protect the cron endpoint with the same secret
    if settings.WEBHOOK_SECRET and x_cron_secret != settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    bot  = await _get_bot()
    done = await process_due_schedules(bot)
    return JSONResponse({"processed": done})


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> JSONResponse:
    try:
        redis = await get_redis()
        await redis.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return JSONResponse({
        "status": "ok" if redis_ok else "degraded",
        "redis":  redis_ok,
    })


# ── One-time webhook registration helper ─────────────────────────────────────

@app.post("/set_webhook")
async def set_webhook(
    x_cron_secret: str | None = Header(default=None),
) -> JSONResponse:
    if settings.WEBHOOK_SECRET and x_cron_secret != settings.WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    bot = await _get_bot()
    url = f"{settings.BASE_URL}{settings.WEBHOOK_PATH}"
    await bot.set_webhook(
        url=url,
        secret_token=settings.WEBHOOK_SECRET,
        allowed_updates=Update.all_types(),
        drop_pending_updates=True,
    )
    info = await bot.get_webhook_info()
    logger.info("Webhook set → %s", url)
    return JSONResponse({"webhook_url": url, "pending": info.pending_update_count})


# ── Shutdown cleanup ──────────────────────────────────────────────────────────

@app.on_event("shutdown")
async def on_shutdown() -> None:
    await close_redis()
    if _bot:
        await _bot.session.close()
