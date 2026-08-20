import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import db_url, init_db_background, schema_ready
from .notify import configured as email_configured
from .routers import (
    activity,
    auth,
    days,
    favourites,
    foods,
    meals,
    notifications,
    settings as settings_router,
)
from .utils import today_str

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
BASE_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = BASE_DIR / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Deliberately not awaited: see db.init_db_background.
    task = asyncio.create_task(init_db_background())
    logger.info("calorie tracker ready (today=%s, tz=%s)", today_str(), settings.app_tz)
    if db_url.startswith("sqlite") and not db_url.startswith("sqlite+aiosqlite:////data/"):
        logger.warning(
            "Using SQLite at %s. On a host without a mounted disk this file "
            "lives inside the container and IS DELETED ON EVERY REDEPLOY. "
            "Set DATABASE_URL to a Postgres URL to keep your data.",
            db_url,
        )
    if not settings.invite_code:
        logger.warning(
            "INVITE_CODE is not set: anyone who finds this URL can create an "
            "account and spend your API credits."
        )
    yield
    task.cancel()


app = FastAPI(title="Calorie Tracker", lifespan=lifespan)

# Only needed for the Vite dev server; in production the SPA is same-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,  # the session cookie must survive the dev proxy
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (
    auth,
    meals,
    days,
    settings_router,
    activity,
    foods,
    favourites,
    notifications,
):
    app.include_router(module.router)


@app.get("/api/health")
async def health():
    # Never echo the connection string -- it carries credentials. Just say
    # enough to answer "will my data survive the next deploy?".
    engine_name = "postgresql" if db_url.startswith("postgresql") else "sqlite"
    on_mounted_volume = engine_name == "sqlite" and db_url.startswith(
        "sqlite+aiosqlite:////data/"
    )
    return {
        "status": "ok",
        "today": today_str(),
        "openai_configured": bool(settings.openai_api_key),
        "model": settings.openai_model,
        "provider": settings.openai_base_url or "https://api.openai.com/v1",
        "invite_required": bool(settings.invite_code),
        "email_configured": email_configured(),
        "cron_enabled": bool(settings.cron_token),
        "database": engine_name,
        "database_ready": schema_ready.is_set(),
        "data_survives_redeploy": engine_name == "postgresql" or on_mounted_volume,
    }


if DIST_DIR.exists():
    app.mount(
        "/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets"
    )

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        candidate = DIST_DIR / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST_DIR / "index.html")
