from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user
from ..db import get_db
from ..models import User
from ..schemas import DayOut, DaySummary
from ..services import build_day, day_summaries
from ..utils import parse_date, today_str

router = APIRouter(prefix="/api/days", tags=["days"])


@router.get("", response_model=list[DaySummary])
async def list_days(
    days: int = Query(30, ge=1, le=365),
    end: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    end_date = end or today_str()
    start_date = (parse_date(end_date) - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    return await day_summaries(db, user.id, start_date, end_date)


@router.get("/{date}", response_model=DayOut)
async def get_day(
    date: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    if date == "today":
        date = today_str()
    return await build_day(db, user.id, date)
