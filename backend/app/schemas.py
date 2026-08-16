from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MealType = Literal["breakfast", "lunch", "dinner", "snacks"]
Unit = Literal["piece", "g", "ml", "bowl", "cup", "tbsp", "slice", "serving"]


class Nutrition(BaseModel):
    calories: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    fiber_g: float = 0
    sugar_g: float = 0
    sodium_mg: float = 0

    def scaled(self, factor: float) -> "Nutrition":
        return Nutrition(
            calories=round(self.calories * factor, 1),
            protein_g=round(self.protein_g * factor, 1),
            carbs_g=round(self.carbs_g * factor, 1),
            fat_g=round(self.fat_g * factor, 1),
            fiber_g=round(self.fiber_g * factor, 1),
            sugar_g=round(self.sugar_g * factor, 1),
            sodium_mg=round(self.sodium_mg * factor, 1),
        )


class ResolvedItem(Nutrition):
    """A food resolved to absolute nutrition, ready to confirm and save."""

    name: str
    normalized_name: str
    quantity: float = 1
    unit: Unit = "serving"
    from_cache: bool = False


class FoodItemOut(ResolvedItem):
    model_config = ConfigDict(from_attributes=True)

    id: int


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1)
    meal_type: MealType


class AnalyzeResponse(BaseModel):
    items: list[ResolvedItem]
    warning: str | None = None


class SaveMealRequest(BaseModel):
    date: str | None = None
    meal_type: MealType
    raw_text: str = ""
    items: list[ResolvedItem]


class MealOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: str
    meal_type: MealType
    raw_text: str = ""
    created_at: datetime
    items: list[FoodItemOut] = []


class MealPatch(BaseModel):
    items: list[ResolvedItem]


class Targets(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    daily_calories: int
    protein_g: int
    carbs_g: int
    fat_g: int
    fiber_g: int
    water_target_ml: int


class SettingsOut(Targets):
    weight_kg: float
    height_cm: float
    age: int
    sex: str
    bmr: float = 0
    tdee: float = 0


class SettingsUpdate(BaseModel):
    daily_calories: int | None = None
    protein_g: int | None = None
    carbs_g: int | None = None
    fat_g: int | None = None
    fiber_g: int | None = None
    water_target_ml: int | None = None
    weight_kg: float | None = None
    height_cm: float | None = None
    age: int | None = None
    sex: str | None = None


class ActivityIn(BaseModel):
    walking_min: float = 0
    tt_min: float = 0


class ActivityOut(ActivityIn):
    date: str
    calories_burned: float = 0
    weight_used_kg: float = 0


class WaterIn(BaseModel):
    ml: float = 0


class WaterOut(WaterIn):
    date: str


class WeightIn(BaseModel):
    date: str | None = None
    weight_kg: float = Field(gt=20, lt=400)


class WeightOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: str
    weight_kg: float


class DayTotals(Nutrition):
    pass


class DayOut(BaseModel):
    date: str
    totals: DayTotals
    targets: Targets
    meals: dict[str, list[MealOut]]
    activity: ActivityOut
    water: WaterOut
    net_calories: float = 0
    weight_kg: float | None = None
    weight_stale_days: int | None = None


class DaySummary(BaseModel):
    date: str
    calories: float = 0
    protein_g: float = 0
    carbs_g: float = 0
    fat_g: float = 0
    fiber_g: float = 0
    burned: float = 0
    weight_kg: float | None = None


class FoodCacheOut(Nutrition):
    model_config = ConfigDict(from_attributes=True)

    id: int
    normalized_name: str
    display_name: str
    unit: Unit
    hit_count: int
    created_at: datetime
    last_used_at: datetime


class FoodCachePatch(BaseModel):
    display_name: str | None = None
    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None
    fiber_g: float | None = None
    sugar_g: float | None = None
    sodium_mg: float | None = None


class PickItem(BaseModel):
    """Add a known food straight from the cache -- no GPT involved."""

    food_id: int
    quantity: float = Field(gt=0, default=1)


class PickRequest(BaseModel):
    date: str | None = None
    meal_type: MealType
    picks: list[PickItem]


class FavouriteOut(BaseModel):
    id: int
    label: str
    meal_type: MealType
    items: list[ResolvedItem]
    total_calories: float = 0


class FavouriteCreate(BaseModel):
    label: str
    meal_type: MealType = "snacks"
    items: list[ResolvedItem]


class LogFavouriteRequest(BaseModel):
    date: str | None = None
    meal_type: MealType | None = None
