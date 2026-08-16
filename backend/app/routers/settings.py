from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user
from ..db import get_db
from ..models import User
from ..exercise import weight_for_date
from ..plan import validate_target_date
from ..schemas import GoalUpdate, PlanOut, SettingsOut, SettingsUpdate
from ..services import current_plan, get_settings_row, settings_out
from ..utils import today_str

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
async def read_settings(
    db: AsyncSession = Depends(get_db), user: User = Depends(current_user)
):
    return settings_out(await get_settings_row(db, user.id))


@router.put("", response_model=SettingsOut)
async def update_settings(
    payload: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    row = await get_settings_row(db, user.id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return settings_out(row)


@router.get("/plan", response_model=PlanOut)
async def read_plan(
    db: AsyncSession = Depends(get_db), user: User = Depends(current_user)
):
    """What your goal costs per day, recomputed against today's weight."""
    return await current_plan(db, user.id)


@router.put("/goal", response_model=PlanOut)
async def update_goal(
    payload: GoalUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    row = await get_settings_row(db, user.id)

    if payload.target_date:
        try:
            validate_target_date(payload.target_date)
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail="Target date must be YYYY-MM-DD"
            ) from exc

    goal_changed = payload.target_weight_kg is not None and (
        payload.target_weight_kg != row.target_weight_kg
    )
    for field in ("target_weight_kg", "target_date", "auto_targets"):
        value = getattr(payload, field)
        if value is not None:
            setattr(row, field, value)

    # Stamp the starting weight on a new goal so "% done" has a baseline.
    # Editing only the date keeps the original baseline.
    if goal_changed or row.goal_start_weight_kg is None:
        row.goal_start_weight_kg = await weight_for_date(db, user.id, today_str())
    await db.commit()

    plan = await current_plan(db, user.id, row)

    # "Apply" writes the recommendation into your saved targets, so it stays
    # put even if you later turn auto-adjust off.
    if payload.apply_now and plan.recommended:
        for field, value in plan.recommended.model_dump().items():
            setattr(row, field, value)
        await db.commit()

    return plan


@router.delete("/goal", response_model=PlanOut)
async def clear_goal(
    db: AsyncSession = Depends(get_db), user: User = Depends(current_user)
):
    row = await get_settings_row(db, user.id)
    row.target_weight_kg = None
    row.target_date = None
    row.auto_targets = False
    row.goal_start_weight_kg = None
    await db.commit()
    return await current_plan(db, user.id, row)
