"""The endpoint a scheduler calls once a day.

Kept out of the browser's reach with a shared token rather than a session,
because the caller is a cron job, not a signed-in person.
"""

import logging
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user
from ..config import get_settings
from ..db import get_db
from ..models import User, UserSettings
from ..notify import NotifyError, compose, configured, send
from ..services import build_day
from ..utils import today_str

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/notifications", tags=["notifications"])
settings = get_settings()


def check_token(token: str | None) -> None:
    if not settings.cron_token:
        raise HTTPException(status_code=503, detail="CRON_TOKEN is not configured")
    if not token or not secrets.compare_digest(token, settings.cron_token):
        raise HTTPException(status_code=403, detail="Bad cron token")


async def _send_for_user(db: AsyncSession, user: User, date: str) -> str:
    day = await build_day(db, user.id, date)
    subject, html, text = compose(day, user.name or "")
    await send(user.email, subject, html, text)
    return user.email


@router.post("/daily")
async def send_daily(
    x_cron_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Email every opted-in user their day so far. One failure must not stop
    the rest, so results are collected per user."""
    check_token(x_cron_token)
    if not configured():
        raise HTTPException(status_code=503, detail="Brevo is not configured")

    date = today_str()
    result = await db.execute(
        select(User, UserSettings)
        .join(UserSettings, UserSettings.user_id == User.id)
        .where(User.is_active.is_(True), UserSettings.daily_email.is_(True))
    )

    sent, failed = [], []
    for user, _ in result.all():
        try:
            sent.append(await _send_for_user(db, user, date))
        except (NotifyError, Exception) as exc:  # noqa: BLE001
            logger.warning("daily email failed for %s: %s", user.email, exc)
            failed.append({"email": user.email, "error": str(exc)[:200]})

    return {"date": date, "sent": len(sent), "failed": failed}


@router.post("/test")
async def send_test(
    db: AsyncSession = Depends(get_db), user: User = Depends(current_user)
):
    """Send yourself the email you'd get tonight, to check it looks right."""
    if not configured():
        raise HTTPException(
            status_code=503,
            detail="Brevo isn't configured: set BREVO_API_KEY and BREVO_SENDER_EMAIL.",
        )
    try:
        await _send_for_user(db, user, today_str())
    except NotifyError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"sent_to": user.email}
