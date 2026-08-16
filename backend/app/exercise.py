"""Exercise burn -- pure arithmetic, no GPT.

kcal = MET * weight_kg * (minutes / 60)

Burn is never stored. It is always derived from the weight that was in effect
on the day in question, so a new weigh-in changes future days without silently
rewriting last month's numbers.
"""

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import UserSettings, WeightLog

DEFAULT_WEIGHT_KG = 86.0

# Compendium of Physical Activities values. Tune here if they feel off.
MET = {
    "walking": 3.5,  # moderate pace, ~5 km/h
    "tt": 4.0,  # table tennis, casual/office
}


def burn(minutes: float, activity: str, weight_kg: float) -> float:
    return round(MET[activity] * weight_kg * (max(minutes, 0) / 60), 1)


def total_burn(walking_min: float, tt_min: float, weight_kg: float) -> float:
    return round(
        burn(walking_min, "walking", weight_kg) + burn(tt_min, "tt", weight_kg), 1
    )


def kcal_per_min(activity: str, weight_kg: float) -> float:
    return round(MET[activity] * weight_kg / 60, 2)


async def weight_for_date(db: AsyncSession, user_id: int, date: str) -> float:
    """Most recent weigh-in on or before `date`, else the profile weight.

    Falling back to the *profile* (not to a later weigh-in) keeps early days
    stable: logging today's weight must not retroactively change January.
    """
    result = await db.execute(
        select(WeightLog)
        .where(WeightLog.user_id == user_id, WeightLog.date <= date)
        .order_by(desc(WeightLog.date))
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is not None:
        return float(row.weight_kg)

    result = await db.execute(
        select(UserSettings).where(UserSettings.user_id == user_id)
    )
    settings_row = result.scalar_one_or_none()
    return float(settings_row.weight_kg) if settings_row else DEFAULT_WEIGHT_KG


# Sedentary on purpose: walking and table tennis are logged and counted as
# burn, so an "active" multiplier here would count them twice. Shared with
# plan.py so Settings and the goal card never show different maintenance.
SEDENTARY_MULTIPLIER = 1.2


def bmr_tdee(weight_kg: float, height_cm: float, age: int, sex: str) -> tuple[float, float]:
    """Mifflin-St Jeor BMR, plus maintenance for a desk job."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    bmr = base + (5 if sex.lower().startswith("m") else -161)
    return round(bmr, 0), round(bmr * SEDENTARY_MULTIPLIER, 0)
