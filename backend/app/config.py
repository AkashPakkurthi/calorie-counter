from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = ""
    database_url: str = "sqlite:///./calories.db"
    app_tz: str = "Asia/Kolkata"

    # Signs session cookies. Left blank a random one is generated at boot,
    # which is fine locally but logs everyone out on every deploy -- set it
    # in production.
    secret_key: str = ""
    # Anyone registering must supply this. Blank disables the gate entirely,
    # which on a public URL means strangers can spend your API credits.
    invite_code: str = ""
    session_days: int = 30
    # Cookies are HTTPS-only unless this is on (needed for plain-HTTP local dev).
    insecure_cookies: bool = False

    # --- daily email (Brevo) ---
    brevo_api_key: str = ""
    brevo_sender_email: str = ""
    brevo_sender_name: str = "Calorie Tracker"
    # Shared secret the scheduled job presents. Without it the endpoint is
    # closed, so nobody can trigger a mail run by guessing the URL.
    cron_token: str = ""
    # Where links in the email point.
    app_url: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
