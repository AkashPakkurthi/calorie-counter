from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..exercise import MET, kcal_per_min
from ..models import ActivityLog, WaterLog, WeightLog
from ..schemas import (
    ActivityIn,
    ActivityOut,
    WaterIn,
    WaterOut,
    WeightIn,
    WeightOut,
)
from ..services import get_activity, get_settings_row, get_water
from ..utils import today_str

router = APIRouter(prefix="/api", tags=["activity"])


@router.get("/activity/rates")
async def activity_rates(db: AsyncSession = Depends(get_db)):
    """kcal/min at your current weight -- shown next to the minute inputs."""
    row = await get_settings_row(db)
    return {
        "weight_kg": row.weight_kg,
        "met": MET,
        "walking_kcal_per_min": kcal_per_min("walking", row.weight_kg),
        "tt_kcal_per_min": kcal_per_min("tt", row.weight_kg),
    }


@router.get("/activity/{date}", response_model=ActivityOut)
async def read_activity(date: str, db: AsyncSession = Depends(get_db)):
    return await get_activity(db, today_str() if date == "today" else date)


@router.put("/activity/{date}", response_model=ActivityOut)
async def set_activity(
    date: str, payload: ActivityIn, db: AsyncSession = Depends(get_db)
):
    date = today_str() if date == "today" else date
    result = await db.execute(select(ActivityLog).where(ActivityLog.date == date))
    row = result.scalar_one_or_none()
    if row is None:
        row = ActivityLog(date=date)
        db.add(row)
    row.walking_min = max(payload.walking_min, 0)
    row.tt_min = max(payload.tt_min, 0)
    await db.commit()
    return await get_activity(db, date)


@router.get("/water/{date}", response_model=WaterOut)
async def read_water(date: str, db: AsyncSession = Depends(get_db)):
    return await get_water(db, today_str() if date == "today" else date)


@router.put("/water/{date}", response_model=WaterOut)
async def set_water(date: str, payload: WaterIn, db: AsyncSession = Depends(get_db)):
    date = today_str() if date == "today" else date
    result = await db.execute(select(WaterLog).where(WaterLog.date == date))
    row = result.scalar_one_or_none()
    if row is None:
        row = WaterLog(date=date)
        db.add(row)
    row.ml = max(payload.ml, 0)
    await db.commit()
    return await get_water(db, date)


@router.get("/weight", response_model=list[WeightOut])
async def list_weights(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WeightLog).order_by(WeightLog.date.desc()))
    return list(result.scalars())


@router.post("/weight", response_model=WeightOut)
async def log_weight(payload: WeightIn, db: AsyncSession = Depends(get_db)):
    """Weekly weigh-in. Also syncs the profile weight so BMR/TDEE and future
    burn calculations follow along."""
    date = payload.date or today_str()
    result = await db.execute(select(WeightLog).where(WeightLog.date == date))
    row = result.scalar_one_or_none()
    if row is None:
        row = WeightLog(date=date)
        db.add(row)
    row.weight_kg = payload.weight_kg

    latest = await db.execute(select(WeightLog).order_by(WeightLog.date.desc()).limit(1))
    newest = latest.scalar_one_or_none()
    if newest is None or date >= newest.date:
        settings_row = await get_settings_row(db)
        settings_row.weight_kg = payload.weight_kg

    await db.commit()
    await db.refresh(row)
    return WeightOut.model_validate(row)


@router.delete("/weight/{weight_id}", status_code=204)
async def delete_weight(weight_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(WeightLog, weight_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Weight entry not found")
    await db.delete(row)
    await db.commit()
