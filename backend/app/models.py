from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

MEAL_TYPES = ("breakfast", "lunch", "dinner", "snacks")


class UserSettings(Base):
    """Single-row table (id=1) holding profile + daily targets."""

    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, default=1)
    daily_calories = Column(Integer, default=2500)
    protein_g = Column(Integer, default=150)
    carbs_g = Column(Integer, default=280)
    fat_g = Column(Integer, default=80)
    fiber_g = Column(Integer, default=30)
    water_target_ml = Column(Integer, default=3000)
    weight_kg = Column(Float, default=86.0)
    height_cm = Column(Float, default=178.0)
    age = Column(Integer, default=26)
    sex = Column(String, default="male")
    # Goal. When both are set, daily targets can be derived from them.
    target_weight_kg = Column(Float, nullable=True)
    target_date = Column(String, nullable=True)  # YYYY-MM-DD
    # Weight when the goal was set -- the only honest baseline for "% done".
    goal_start_weight_kg = Column(Float, nullable=True)
    # Recompute targets from the goal as weight and days-left change, instead
    # of freezing whatever the numbers were on the day you set the goal.
    auto_targets = Column(Boolean, default=False)


class MealEntry(Base):
    __tablename__ = "meal_entries"

    id = Column(Integer, primary_key=True)
    date = Column(String, index=True, nullable=False)  # YYYY-MM-DD, local tz
    meal_type = Column(String, index=True, nullable=False)
    raw_text = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    items = relationship(
        "FoodItem", back_populates="meal", cascade="all, delete-orphan", lazy="selectin"
    )


class FoodItem(Base):
    """A resolved food inside a meal. Nutrition values here are ABSOLUTE
    (already multiplied by quantity)."""

    __tablename__ = "food_items"

    id = Column(Integer, primary_key=True)
    meal_id = Column(Integer, ForeignKey("meal_entries.id", ondelete="CASCADE"), index=True)
    name = Column(String, nullable=False)
    normalized_name = Column(String, index=True, nullable=False)
    quantity = Column(Float, default=1.0)
    unit = Column(String, default="serving")
    calories = Column(Float, default=0.0)
    protein_g = Column(Float, default=0.0)
    carbs_g = Column(Float, default=0.0)
    fat_g = Column(Float, default=0.0)
    fiber_g = Column(Float, default=0.0)
    sugar_g = Column(Float, default=0.0)
    sodium_mg = Column(Float, default=0.0)
    from_cache = Column(Boolean, default=False)

    meal = relationship("MealEntry", back_populates="items")


class FoodCache(Base):
    """Per-ONE-unit nutrition memory, so repeat foods never hit GPT again."""

    __tablename__ = "food_cache"
    __table_args__ = (UniqueConstraint("normalized_name", "unit", name="uq_food_unit"),)

    id = Column(Integer, primary_key=True)
    normalized_name = Column(String, index=True, nullable=False)
    display_name = Column(String, nullable=False)
    unit = Column(String, nullable=False)
    calories = Column(Float, default=0.0)
    protein_g = Column(Float, default=0.0)
    carbs_g = Column(Float, default=0.0)
    fat_g = Column(Float, default=0.0)
    fiber_g = Column(Float, default=0.0)
    sugar_g = Column(Float, default=0.0)
    sodium_mg = Column(Float, default=0.0)
    hit_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    last_used_at = Column(DateTime, default=lambda: datetime.now(UTC))


class Favourite(Base):
    __tablename__ = "favourites"

    id = Column(Integer, primary_key=True)
    label = Column(String, nullable=False)
    meal_type = Column(String, default="snacks")
    items_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


class ActivityLog(Base):
    """Minutes only -- calories burned is derived at read time from the
    weight in effect on that date."""

    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True)
    date = Column(String, unique=True, index=True, nullable=False)
    walking_min = Column(Float, default=0.0)
    tt_min = Column(Float, default=0.0)


class WeightLog(Base):
    __tablename__ = "weight_log"

    id = Column(Integer, primary_key=True)
    date = Column(String, unique=True, index=True, nullable=False)
    weight_kg = Column(Float, nullable=False)


class WaterLog(Base):
    __tablename__ = "water_log"

    id = Column(Integer, primary_key=True)
    date = Column(String, unique=True, index=True, nullable=False)
    ml = Column(Float, default=0.0)
