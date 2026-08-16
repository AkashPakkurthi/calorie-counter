from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..schemas import SettingsOut, SettingsUpdate
from ..services import get_settings_row, settings_out

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
async def read_settings(db: AsyncSession = Depends(get_db)):
    return settings_out(await get_settings_row(db))


@router.put("", response_model=SettingsOut)
async def update_settings(payload: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    row = await get_settings_row(db)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return settings_out(row)
