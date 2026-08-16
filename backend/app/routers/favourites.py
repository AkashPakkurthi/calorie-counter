import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import Favourite
from ..schemas import (
    FavouriteCreate,
    FavouriteOut,
    LogFavouriteRequest,
    MealOut,
    ResolvedItem,
)
from ..services import save_meal
from ..utils import today_str

router = APIRouter(prefix="/api/favourites", tags=["favourites"])


def _to_out(row: Favourite) -> FavouriteOut:
    items = [ResolvedItem(**i) for i in json.loads(row.items_json)]
    return FavouriteOut(
        id=row.id,
        label=row.label,
        meal_type=row.meal_type,
        items=items,
        total_calories=round(sum(i.calories for i in items), 1),
    )


@router.get("", response_model=list[FavouriteOut])
async def list_favourites(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Favourite).order_by(desc(Favourite.created_at)))
    return [_to_out(row) for row in result.scalars()]


@router.post("", response_model=FavouriteOut)
async def create_favourite(payload: FavouriteCreate, db: AsyncSession = Depends(get_db)):
    row = Favourite(
        label=payload.label,
        meal_type=payload.meal_type,
        items_json=json.dumps([i.model_dump() for i in payload.items]),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.post("/{fav_id}/log", response_model=MealOut)
async def log_favourite(
    fav_id: int,
    payload: LogFavouriteRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Re-add a saved meal with zero GPT calls."""
    row = await db.get(Favourite, fav_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Favourite not found")
    payload = payload or LogFavouriteRequest()
    fav = _to_out(row)
    meal = await save_meal(
        db,
        payload.date or today_str(),
        payload.meal_type or row.meal_type,
        f"favourite: {row.label}",
        fav.items,
    )
    return MealOut.model_validate(meal)


@router.delete("/{fav_id}", status_code=204)
async def delete_favourite(fav_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(Favourite, fav_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Favourite not found")
    await db.delete(row)
    await db.commit()
