from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import (
    check_invite,
    clear_session,
    current_user,
    get_user_by_email,
    hash_password,
    normalize_email,
    set_session,
    verify_password,
)
from ..config import get_settings
from ..db import get_db
from ..models import User, WeightLog
from ..schemas import LoginRequest, RegisterRequest, UserOut
from ..plan import build_plan
from ..services import get_settings_row
from ..utils import today_str

router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


@router.get("/config")
async def auth_config():
    """Lets the login screen know whether to show the invite-code field."""
    return {"invite_required": bool(settings.invite_code)}


@router.post("/register", response_model=UserOut)
async def register(
    payload: RegisterRequest, response: Response, db: AsyncSession = Depends(get_db)
):
    check_invite(payload.invite_code)

    if await get_user_by_email(db, payload.email):
        raise HTTPException(status_code=409, detail="That email is already registered")

    user = User(
        email=normalize_email(payload.email),
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Seed the profile from the signup form and start them at maintenance,
    # so the dashboard is meaningful before they set a goal.
    row = await get_settings_row(db, user.id)
    row.age = payload.age
    row.sex = payload.sex
    row.height_cm = payload.height_cm
    row.weight_kg = payload.weight_kg
    plan = build_plan(
        current_weight=payload.weight_kg,
        height_cm=payload.height_cm,
        age=payload.age,
        sex=payload.sex,
        target_weight=None,
        target_date=None,
    )
    for field, value in plan.recommended.items():
        setattr(row, field, value)
    db.add(WeightLog(user_id=user.id, date=today_str(), weight_kg=payload.weight_kg))
    await db.commit()
    set_session(response, user.id)
    return UserOut.model_validate(user)


@router.post("/login", response_model=UserOut)
async def login(
    payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
):
    user = await get_user_by_email(db, payload.email)
    # Same message either way: don't reveal which emails exist.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled")

    set_session(response, user.id)
    return UserOut.model_validate(user)


@router.post("/logout", status_code=204)
async def logout(response: Response):
    clear_session(response)


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(current_user)):
    return UserOut.model_validate(user)
