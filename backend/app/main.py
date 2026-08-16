import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import async_session, init_db
from .routers import activity, days, favourites, foods, meals, settings as settings_router
from .services import get_settings_row
from .utils import today_str

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
BASE_DIR = Path(__file__).resolve().parents[2]
DIST_DIR = BASE_DIR / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with async_session() as session:
        await get_settings_row(session)  # seed the single settings row
    logger.info("calorie tracker ready (today=%s, tz=%s)", today_str(), settings.app_tz)
    yield


app = FastAPI(title="Calorie Tracker", lifespan=lifespan)

# Only needed for the Vite dev server; in production the SPA is same-origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (meals, days, settings_router, activity, foods, favourites):
    app.include_router(module.router)


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "today": today_str(),
        "openai_configured": bool(settings.openai_api_key),
        "model": settings.openai_model,
        "provider": settings.openai_base_url or "https://api.openai.com/v1",
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
