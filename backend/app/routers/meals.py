from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import current_user
from ..db import get_db
from ..models import FoodCache, FoodItem, MealEntry, User
from ..nutrition import NutritionError, resolve_meal
from ..schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    MealOut,
    MealPatch,
    PickRequest,
    ResolvedItem,
    SaveMealRequest,
)
from ..services import NUTRIENTS, save_meal
from ..utils import today_str

router = APIRouter(prefix="/api/meals", tags=["meals"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    payload: AnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """Free text -> resolved items. Writes nothing to your meal history;
    you confirm (and can edit) before anything is saved."""
    try:
        items = await resolve_meal(db, user.id, payload.text, payload.meal_type)
    except NutritionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not items:
        raise HTTPException(status_code=422, detail="Could not identify any food in that text.")

    # Don't hide a dubious estimate -- flag it so it gets checked before saving.
    suspect = [f"{i.name} ({note})" for i in items if (note := i.implausible())]
    warning = (
        "These look off, please double-check: " + "; ".join(suspect) if suspect else None
    )
    return AnalyzeResponse(items=items, warning=warning)


@router.post("", response_model=MealOut)
async def create_meal(
    payload: SaveMealRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    meal = await save_meal(
        db,
        user.id,
        payload.date or today_str(),
        payload.meal_type,
        payload.raw_text,
        payload.items,
    )
    return MealOut.model_validate(meal)


@router.post("/pick", response_model=MealOut)
async def create_from_picks(
    payload: PickRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    """Log known foods straight from the cache -- no GPT call, no cost."""
    if not payload.picks:
        raise HTTPException(status_code=422, detail="No foods selected.")

    items: list[ResolvedItem] = []
    for pick in payload.picks:
        food = await db.get(FoodCache, pick.food_id)
        if food is None or food.user_id != user.id:
            raise HTTPException(status_code=404, detail=f"Unknown food id {pick.food_id}")
        per_unit = {k: getattr(food, k) or 0 for k in NUTRIENTS}
        scaled = {k: round(v * pick.quantity, 1) for k, v in per_unit.items()}
        items.append(
            ResolvedItem(
                name=food.display_name,
                normalized_name=food.normalized_name,
                quantity=pick.quantity,
                unit=food.unit,
                from_cache=True,
                **scaled,
            )
        )

    labels = ", ".join(f"{i.quantity:g} {i.unit} {i.name}" for i in items)
    meal = await save_meal(
        db, user.id, payload.date or today_str(), payload.meal_type, labels, items
    )
    return MealOut.model_validate(meal)


@router.patch("/{meal_id}", response_model=MealOut)
async def update_meal(
    meal_id: int,
    payload: MealPatch,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    meal = await db.get(MealEntry, meal_id)
    # 404 rather than 403 on someone else's row: don't confirm it exists.
    if meal is None or meal.user_id != user.id:
        raise HTTPException(status_code=404, detail="Meal not found")

    for item in list(meal.items):
        await db.delete(item)
    await db.flush()

    for item in payload.items:
        db.add(
            FoodItem(
                meal_id=meal.id,
                name=item.name,
                normalized_name=item.normalized_name,
                quantity=item.quantity,
                unit=item.unit,
                from_cache=item.from_cache,
                **{k: getattr(item, k) for k in NUTRIENTS},
            )
        )
    await db.commit()
    await db.refresh(meal)
    return MealOut.model_validate(meal)


@router.delete("/{meal_id}", status_code=204)
async def delete_meal(
    meal_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(current_user),
):
    meal = await db.get(MealEntry, meal_id)
    if meal is None or meal.user_id != user.id:
        raise HTTPException(status_code=404, detail="Meal not found")
    await db.delete(meal)
    await db.commit()
