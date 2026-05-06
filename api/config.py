"""
Central configuration — loaded once, cached forever.
All values come from environment variables or .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Telegram ────────────────────────────────────────────────────────────
    BOT_TOKEN: str
    BOT_USERNAME: str          # without @, e.g. "mybot"
    ADMIN_ID: int              # Telegram user-id of the admin

    # ── Redis (Upstash or any Redis-compatible URL) ──────────────────────
    REDIS_URL: str             # rediss://... or redis://...

    # ── Webhook ─────────────────────────────────────────────────────────
    BASE_URL: str = "https://your-project.vercel.app"
    WEBHOOK_PATH: str = "/webhook"
    WEBHOOK_SECRET: str = "change_me_in_production"

    # ── Optional channel to auto-publish posters ─────────────────────────
    DEFAULT_CHANNEL_ID: int = 0   # 0 = disabled

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
