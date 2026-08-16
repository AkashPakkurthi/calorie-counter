from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import FoodCache
from ..schemas import FoodCacheOut, FoodCachePatch

router = APIRouter(prefix="/api/foods", tags=["foods"])


@router.get("/options", response_model=list[FoodCacheOut])
async def food_options(
    q: str | None = Query(None, description="substring filter"),
    limit: int = Query(200, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """Everything the tracker already knows, for the 'Pick' adder.
    Most-used first, so your regulars are at the top. No GPT involved."""
    stmt = select(FoodCache)
    if q:
        pattern = f"%{q.lower().strip()}%"
        stmt = stmt.where(
            or_(FoodCache.normalized_name.like(pattern), FoodCache.display_name.ilike(pattern))
        )
    stmt = stmt.order_by(desc(FoodCache.hit_count), desc(FoodCache.last_used_at)).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars())


@router.get("", response_model=list[FoodCacheOut])
async def list_foods(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(FoodCache).order_by(desc(FoodCache.hit_count), FoodCache.normalized_name)
    )
    return list(result.scalars())


@router.patch("/{food_id}", response_model=FoodCacheOut)
async def update_food(
    food_id: int, payload: FoodCachePatch, db: AsyncSession = Depends(get_db)
):
    """Fix a bad estimate once and every future meal uses the corrected value."""
    row = await db.get(FoodCache, food_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Food not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(row, field, value)
    await db.commit()
    await db.refresh(row)
    return FoodCacheOut.model_validate(row)


@router.delete("/{food_id}", status_code=204)
async def delete_food(food_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.get(FoodCache, food_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Food not found")
    await db.delete(row)
    await db.commit()
