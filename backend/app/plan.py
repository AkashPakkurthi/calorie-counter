"""Turn a goal -- "reach X kg by date Y" -- into daily targets.

Pure functions so the arithmetic is testable without a database.

The energy model deliberately keeps two things separate:
  * `maintenance` uses a SEDENTARY multiplier, because walking and table
    tennis are logged explicitly and counted as burn. Using an "active"
    multiplier here would count that exercise twice.
  * the deficit is applied to maintenance; whatever you actually burn on the
    day is then extra headroom, which the dashboard already shows as net.
"""

from dataclasses import dataclass, field

from .exercise import SEDENTARY_MULTIPLIER, bmr_tdee
from .utils import days_between, parse_date, today_str

KCAL_PER_KG = 7700  # energy in a kilo of body fat, the standard planning figure
SEDENTARY = SEDENTARY_MULTIPLIER  # desk job; logged exercise added separately
MAX_SAFE_KG_PER_WEEK = 1.0
ABSOLUTE_FLOOR_KCAL = 1500  # below this, an adult male tends to lose muscle
# Sitting a little under BMR is normal in a cut; sitting far under it is not.
BMR_FLOOR_FRACTION = 0.9
MAX_SURPLUS = 500  # a bulk faster than this is mostly fat


@dataclass
class Plan:
    current_weight: float
    start_weight: float | None = None
    progress_pct: float = 0.0
    target_weight: float | None = None
    target_date: str | None = None
    days_left: int = 0
    kg_to_go: float = 0.0
    weekly_rate: float = 0.0
    maintenance: float = 0.0
    daily_delta: float = 0.0
    recommended: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    achievable: bool = True


def macro_split(calories: float, weight_kg: float, cutting: bool) -> dict:
    """Protein first (it protects muscle in a deficit), then fat at 25% of
    energy, then carbs take whatever is left."""
    protein_g = round(min(2.0 if cutting else 1.8, 2.2) * weight_kg)
    fat_g = round(calories * 0.25 / 9)
    remaining = calories - (protein_g * 4) - (fat_g * 9)
    carbs_g = max(round(remaining / 4), 0)
    return {
        "daily_calories": round(calories),
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fat_g": fat_g,
        "fiber_g": max(round(calories / 1000 * 14), 25),  # ~14 g per 1000 kcal
    }


def build_plan(
    current_weight: float,
    height_cm: float,
    age: int,
    sex: str,
    target_weight: float | None,
    target_date: str | None,
    start_weight: float | None = None,
    today: str | None = None,
) -> Plan:
    bmr, _ = bmr_tdee(current_weight, height_cm, age, sex)
    maintenance = round(bmr * SEDENTARY)
    plan = Plan(current_weight=current_weight, maintenance=maintenance)

    if not target_weight or not target_date:
        plan.recommended = macro_split(maintenance, current_weight, cutting=False)
        plan.daily_delta = 0
        return plan

    today = today or today_str()
    plan.target_weight = target_weight
    plan.target_date = target_date
    plan.start_weight = start_weight or current_weight
    total = plan.start_weight - target_weight
    if abs(total) > 0.05:
        done = (plan.start_weight - current_weight) / total
        plan.progress_pct = round(max(0.0, min(1.0, done)) * 100, 1)
    plan.days_left = days_between(today, target_date)
    plan.kg_to_go = round(current_weight - target_weight, 1)

    if plan.days_left <= 0:
        plan.warnings.append(
            "That date has passed — pick a new one to get a fresh plan."
        )
        plan.achievable = False
        plan.recommended = macro_split(maintenance, current_weight, cutting=False)
        return plan

    weeks = plan.days_left / 7
    plan.weekly_rate = round(plan.kg_to_go / weeks, 2)
    plan.daily_delta = round(plan.kg_to_go * KCAL_PER_KG / plan.days_left)

    cutting = plan.kg_to_go > 0
    calories = maintenance - plan.daily_delta

    if abs(plan.weekly_rate) > MAX_SAFE_KG_PER_WEEK:
        plan.warnings.append(
            f"{abs(plan.weekly_rate)} kg/week is faster than the ~1 kg/week that is "
            "usually sustainable. Consider a later date."
        )

    floor = max(ABSOLUTE_FLOOR_KCAL, round(bmr * BMR_FLOOR_FRACTION))
    if cutting and calories < floor:
        plan.achievable = False
        realistic_days = round(plan.kg_to_go * KCAL_PER_KG / (maintenance - floor))
        plan.warnings.append(
            f"Hitting that needs {round(calories)} kcal/day, below your floor of "
            f"{round(floor)}. Capped at the floor — at that rate you'd need about "
            f"{realistic_days} days."
        )
        calories = floor
    elif not cutting and plan.daily_delta < -MAX_SURPLUS:
        plan.achievable = False
        plan.warnings.append(
            f"That's a {abs(plan.daily_delta)} kcal/day surplus; capped at "
            f"{MAX_SURPLUS} to keep the gain mostly lean."
        )
        calories = maintenance + MAX_SURPLUS

    plan.recommended = macro_split(calories, current_weight, cutting=cutting)
    return plan


def validate_target_date(value: str) -> str:
    parse_date(value)  # raises if malformed
    return value
