"""Email + password auth for a small multi-user app.

Sessions are a signed, expiring cookie rather than a JWT: there is no third
party to hand a token to, and an httpOnly cookie keeps it out of reach of any
JavaScript on the page.
"""

import logging
import secrets

import bcrypt
from fastapi import Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .db import get_db
from .models import User

logger = logging.getLogger(__name__)
settings = get_settings()

COOKIE_NAME = "calorie_session"
SALT = "calorie-session-v1"

_secret = settings.secret_key
if not _secret:
    _secret = secrets.token_urlsafe(32)
    logger.warning(
        "SECRET_KEY is not set; generated a temporary one. Everyone will be "
        "logged out whenever the server restarts."
    )

serializer = URLSafeTimedSerializer(_secret, salt=SALT)


def hash_password(password: str) -> str:
    # bcrypt silently truncates past 72 bytes; reject rather than mislead.
    if len(password.encode()) > 72:
        raise HTTPException(status_code=422, detail="Password is too long (max 72 bytes)")
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def normalize_email(email: str) -> str:
    return email.strip().lower()


def check_invite(code: str | None) -> None:
    if not settings.invite_code:
        return  # gate disabled
    if not code or not secrets.compare_digest(code.strip(), settings.invite_code):
        raise HTTPException(status_code=403, detail="Invalid invite code")


def set_session(response: Response, user_id: int) -> None:
    response.set_cookie(
        COOKIE_NAME,
        serializer.dumps({"uid": user_id}),
        max_age=settings.session_days * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=not settings.insecure_cookies,
        path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def read_session(request: Request) -> int | None:
    raw = request.cookies.get(COOKIE_NAME)
    if not raw:
        return None
    try:
        data = serializer.loads(raw, max_age=settings.session_days * 24 * 3600)
    except (BadSignature, SignatureExpired):
        return None
    return data.get("uid")


async def current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    """Every data route depends on this -- no session, no data."""
    user_id = read_session(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Not signed in")
    return user


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(func.lower(User.email) == normalize_email(email))
    )
    return result.scalar_one_or_none()
