"""Shared write/read helpers used by more than one router."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .exercise import bmr_tdee, total_burn, weight_for_date
from .models import (
    ActivityLog,
    FoodItem,
    MealEntry,
    UserSettings,
    WaterLog,
    WeightLog,
)
from .nutrition import per_unit_from_absolute, upsert_cache
from .plan import build_plan
from .schemas import (
    ActivityOut,
    PlanOut,
    DayOut,
    DaySummary,
    DayTotals,
    MealOut,
    ResolvedItem,
    SettingsOut,
    Targets,
    WaterOut,
)
from .utils import days_between, today_str

MEAL_TYPES = ("breakfast", "lunch", "dinner", "snacks")
NUTRIENTS = (
    "calories",
    "protein_g",
    "carbs_g",
    "fat_g",
    "fiber_g",
    "sugar_g",
    "sodium_mg",
)


async def get_settings_row(db: AsyncSession) -> UserSettings:
    row = await db.get(UserSettings, 1)
    if row is None:
        row = UserSettings(id=1)
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return row


async def current_plan(db: AsyncSession, row: UserSettings | None = None) -> PlanOut:
    """The goal, costed out against the weight you are today."""
    row = row or await get_settings_row(db)
    weight = await weight_for_date(db, today_str())
    plan = build_plan(
        current_weight=weight,
        height_cm=row.height_cm,
        age=row.age,
        sex=row.sex,
        target_weight=row.target_weight_kg,
        target_date=row.target_date,
        start_weight=row.goal_start_weight_kg,
    )
    data = plan.__dict__ | {
        "recommended": Targets(
            **plan.recommended, water_target_ml=row.water_target_ml
        )
        if plan.recommended
        else None
    }
    return PlanOut(**data)


async def effective_targets(db: AsyncSession, row: UserSettings) -> Targets:
    """Targets as the dashboard should show them: derived from the goal when
    auto_targets is on, otherwise the numbers you typed in."""
    if row.auto_targets and row.target_weight_kg and row.target_date:
        plan = await current_plan(db, row)
        if plan.recommended:
            return plan.recommended
    return Targets.model_validate(row)


def settings_out(row: UserSettings) -> SettingsOut:
    bmr, tdee = bmr_tdee(row.weight_kg, row.height_cm, row.age, row.sex)
    return SettingsOut(
        daily_calories=row.daily_calories,
        protein_g=row.protein_g,
        carbs_g=row.carbs_g,
        fat_g=row.fat_g,
        fiber_g=row.fiber_g,
        water_target_ml=row.water_target_ml,
        weight_kg=row.weight_kg,
        height_cm=row.height_cm,
        age=row.age,
        sex=row.sex,
        bmr=bmr,
        tdee=tdee,
        target_weight_kg=row.target_weight_kg,
        target_date=row.target_date,
        auto_targets=bool(row.auto_targets),
    )


async def save_meal(
    db: AsyncSession,
    date: str,
    meal_type: str,
    raw_text: str,
    items: list[ResolvedItem],
    teach_cache: bool = True,
) -> MealEntry:
    """Persist a confirmed meal. Also teaches the food cache, so any
    correction you made on the confirm screen sticks for next time."""
    meal = MealEntry(date=date, meal_type=meal_type, raw_text=raw_text)
    db.add(meal)
    await db.flush()

    for item in items:
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
        if teach_cache:
            await upsert_cache(
                db,
                item.normalized_name,
                item.name,
                item.unit,
                per_unit_from_absolute(item),
                bump=True,
            )

    await db.commit()
    await db.refresh(meal)
    return meal


def sum_items(items) -> DayTotals:
    totals = {k: 0.0 for k in NUTRIENTS}
    for item in items:
        for key in NUTRIENTS:
            totals[key] += getattr(item, key) or 0
    return DayTotals(**{k: round(v, 1) for k, v in totals.items()})


async def get_activity(db: AsyncSession, date: str) -> ActivityOut:
    result = await db.execute(select(ActivityLog).where(ActivityLog.date == date))
    row = result.scalar_one_or_none()
    walking = row.walking_min if row else 0.0
    tt = row.tt_min if row else 0.0
    weight = await weight_for_date(db, date)
    return ActivityOut(
        date=date,
        walking_min=walking,
        tt_min=tt,
        calories_burned=total_burn(walking, tt, weight),
        weight_used_kg=weight,
    )


async def get_water(db: AsyncSession, date: str) -> WaterOut:
    result = await db.execute(select(WaterLog).where(WaterLog.date == date))
    row = result.scalar_one_or_none()
    return WaterOut(date=date, ml=row.ml if row else 0.0)


async def latest_weight_entry(db: AsyncSession) -> WeightLog | None:
    result = await db.execute(select(WeightLog).order_by(WeightLog.date.desc()).limit(1))
    return result.scalar_one_or_none()


async def build_day(db: AsyncSession, date: str) -> DayOut:
    result = await db.execute(
        select(MealEntry).where(MealEntry.date == date).order_by(MealEntry.created_at)
    )
    meals = list(result.scalars())

    grouped: dict[str, list[MealOut]] = {m: [] for m in MEAL_TYPES}
    all_items = []
    for meal in meals:
        grouped.setdefault(meal.meal_type, []).append(MealOut.model_validate(meal))
        all_items.extend(meal.items)

    totals = sum_items(all_items)
    settings_row = await get_settings_row(db)
    activity = await get_activity(db, date)

    latest = await latest_weight_entry(db)
    stale = days_between(latest.date, today_str()) if latest else None

    return DayOut(
        date=date,
        totals=totals,
        targets=await effective_targets(db, settings_row),
        meals=grouped,
        activity=activity,
        water=await get_water(db, date),
        net_calories=round(totals.calories - activity.calories_burned, 1),
        weight_kg=activity.weight_used_kg,
        weight_stale_days=stale,
    )


async def day_summaries(db: AsyncSession, start: str, end: str) -> list[DaySummary]:
    result = await db.execute(
        select(MealEntry).where(MealEntry.date >= start, MealEntry.date <= end)
    )
    by_date: dict[str, list] = {}
    for meal in result.scalars():
        by_date.setdefault(meal.date, []).extend(meal.items)

    activity_rows = await db.execute(
        select(ActivityLog).where(ActivityLog.date >= start, ActivityLog.date <= end)
    )
    activity = {r.date: r for r in activity_rows.scalars()}

    weight_rows = await db.execute(
        select(WeightLog).where(WeightLog.date >= start, WeightLog.date <= end)
    )
    weights = {r.date: r.weight_kg for r in weight_rows.scalars()}

    dates = sorted(set(by_date) | set(activity) | set(weights))
    out = []
    for date in dates:
        totals = sum_items(by_date.get(date, []))
        act = activity.get(date)
        burned = 0.0
        if act:
            burned = total_burn(
                act.walking_min, act.tt_min, await weight_for_date(db, date)
            )
        out.append(
            DaySummary(
                date=date,
                calories=totals.calories,
                protein_g=totals.protein_g,
                carbs_g=totals.carbs_g,
                fat_g=totals.fat_g,
                fiber_g=totals.fiber_g,
                burned=burned,
                weight_kg=weights.get(date),
            )
        )
    return out
