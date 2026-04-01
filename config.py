"""
config.py  —  All environment variables & app settings in one place.
Load with:  from config import settings
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Supabase ──────────────────────────────────────────────
    supabase_url: str
    supabase_service_key: str          # Service role — server only, never exposed
    supabase_anon_key: str             # Anon key — safe for public reads

    # ── Paystack ─────────────────────────────────────────────
    paystack_secret_key: str           # sk_live_… or sk_test_…
    paystack_webhook_secret: str       # Webhook hash secret from dashboard

    # ── Resend (Email) ────────────────────────────────────────
    resend_api_key: str
    email_from: str = "bookings@yourdomain.com"

    # ── Admin ─────────────────────────────────────────────────
    admin_username: str = "admin"
    admin_password: str                # Strong password — store in .env
    admin_secret_token: str            # Random 64-char string for JWT signing

    # ── App ───────────────────────────────────────────────────
    app_name: str = "Booking Site"
    debug: bool = False
    allowed_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings — evaluated once at startup."""
    return Settings()


settings = get_settings()
