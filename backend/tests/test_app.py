import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_calories.db")

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from backend.app.exercise import bmr_tdee, total_burn, weight_for_date  # noqa: E402
from backend.app.models import Base, UserSettings, WeightLog  # noqa: E402
from backend.app.nutrition import per_unit_from_absolute, upsert_cache  # noqa: E402
from backend.app.schemas import Nutrition, ResolvedItem  # noqa: E402
from backend.app.services import build_day, save_meal  # noqa: E402
from backend.app.utils import normalize, today_str  # noqa: E402

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(UserSettings(id=1, weight_kg=86.0))
        await session.commit()
        yield session
    await engine.dispose()


def item(name, qty=1, unit="piece", **kw):
    base = dict(calories=100, protein_g=3, carbs_g=20, fat_g=1, fiber_g=2, sugar_g=1, sodium_mg=150)
    base.update(kw)
    return ResolvedItem(
        name=name, normalized_name=normalize(name), quantity=qty, unit=unit, **base
    )


# --- exercise math -------------------------------------------------------


def test_burn_formula():
    # 60 min walking at MET 3.5, 86 kg -> 3.5 * 86 = 301 kcal
    assert total_burn(60, 0, 86) == 301.0
    # 30 min table tennis at MET 4.0, 86 kg -> 4 * 86 * 0.5 = 172
    assert total_burn(0, 30, 86) == 172.0
    assert total_burn(0, 0, 86) == 0.0


def test_burn_scales_with_weight():
    assert total_burn(60, 0, 80) < total_burn(60, 0, 86)


def test_bmr_tdee():
    bmr, tdee = bmr_tdee(86, 178, 26, "male")
    assert bmr == 1848  # 10*86 + 6.25*178 - 5*26 + 5
    assert tdee > bmr


# --- weight_for_date -----------------------------------------------------


async def test_weight_falls_back_to_profile(db):
    assert await weight_for_date(db, "2026-01-01") == 86.0


async def test_weight_uses_entry_in_effect_on_that_date(db):
    db.add_all(
        [
            WeightLog(date="2026-01-04", weight_kg=86.0),
            WeightLog(date="2026-02-01", weight_kg=82.0),
        ]
    )
    await db.commit()

    # A day between weigh-ins uses the earlier one...
    assert await weight_for_date(db, "2026-01-20") == 86.0
    # ...a day after the newer one uses the newer weight...
    assert await weight_for_date(db, "2026-02-10") == 82.0
    # ...and a day before any weigh-in falls back to the profile, so a new
    # weigh-in never retroactively rewrites older days.
    assert await weight_for_date(db, "2025-12-25") == 86.0


async def test_old_day_burn_unchanged_by_new_weigh_in(db):
    db.add(WeightLog(date="2026-01-04", weight_kg=86.0))
    await db.commit()
    before = total_burn(60, 0, await weight_for_date(db, "2026-01-10"))

    db.add(WeightLog(date="2026-06-01", weight_kg=78.0))
    await db.commit()
    after = total_burn(60, 0, await weight_for_date(db, "2026-01-10"))

    assert before == after
    assert total_burn(60, 0, await weight_for_date(db, "2026-06-05")) < before


# --- cache ---------------------------------------------------------------


async def test_saving_a_meal_teaches_the_cache(db):
    date = today_str()
    await save_meal(db, date, "lunch", "3 rotis", [item("Roti", qty=3, calories=300, protein_g=9)])

    from sqlalchemy import select

    from backend.app.models import FoodCache

    row = (await db.execute(select(FoodCache))).scalar_one()
    # Absolute 300 kcal for 3 rotis must be stored as 100 kcal PER ROTI.
    assert row.calories == 100
    assert row.protein_g == 3
    assert row.hit_count == 1


async def test_per_unit_inversion_roundtrip():
    per_unit = per_unit_from_absolute(item("Roti", qty=4, calories=400, protein_g=12))
    assert per_unit.calories == 100
    assert per_unit.protein_g == 3
    assert per_unit.scaled(4).calories == 400


async def test_upsert_overwrites_and_bumps(db):
    await upsert_cache(db, "roti", "Roti", "piece", Nutrition(calories=100), bump=True)
    row = await upsert_cache(db, "roti", "Roti", "piece", Nutrition(calories=120), bump=True)
    await db.commit()
    assert row.calories == 120  # a correction sticks
    assert row.hit_count == 2


# --- day aggregation -----------------------------------------------------


async def test_day_totals_and_net_calories(db):
    date = today_str()
    await save_meal(db, date, "breakfast", "", [item("Idli", qty=2, calories=140, protein_g=4)])
    await save_meal(db, date, "lunch", "", [item("Rice", qty=1, unit="bowl", calories=260, protein_g=5)])

    from backend.app.models import ActivityLog

    db.add(ActivityLog(date=date, walking_min=60, tt_min=0))
    await db.commit()

    day = await build_day(db, date)
    assert day.totals.calories == 400
    assert day.totals.protein_g == 9
    assert day.activity.calories_burned == 301.0
    assert day.net_calories == 99.0
    assert len(day.meals["breakfast"]) == 1
    assert day.targets.daily_calories == 2500


async def test_empty_day_is_zeroed_not_an_error(db):
    day = await build_day(db, "2026-03-01")
    assert day.totals.calories == 0
    assert day.net_calories == 0
    assert day.meals["dinner"] == []


def test_today_is_local_and_well_formed():
    assert len(today_str()) == 10 and today_str().count("-") == 2


# --- provider quirks: JSON mode, per-100 basis, sanity check ---------------

from backend.app import nutrition  # noqa: E402


def test_extract_json_survives_fences_and_prose():
    assert nutrition._extract_json('{"a": 1}') == {"a": 1}
    assert nutrition._extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert nutrition._extract_json('Sure!\n{"a": 1}\nHope that helps.') == {"a": 1}


def test_detects_provider_rejecting_json_schema():
    groq = Exception(
        "Error code: 400 - This model does not support response format `json_schema`."
    )
    assert nutrition._unsupported_schema_error(groq)
    assert not nutrition._unsupported_schema_error(Exception("rate limit exceeded"))


async def test_gram_and_ml_foods_are_converted_from_a_per_100_basis(monkeypatch):
    async def fake_chat(system, user, schema):
        return {
            "foods": [
                # per 100 ml, the basis the prompt asks for
                {"normalized_name": "buttermilk", "unit": "ml", "calories": 40,
                 "protein_g": 3.5, "carbs_g": 6.5, "fat_g": 1.0, "fiber_g": 0,
                 "sugar_g": 5, "sodium_mg": 100},
                # per one piece -- must NOT be divided
                {"normalized_name": "roti", "unit": "piece", "calories": 104,
                 "protein_g": 3.1, "carbs_g": 18, "fat_g": 2.4, "fiber_g": 1.6,
                 "sugar_g": 0.4, "sodium_mg": 190},
            ]
        }

    monkeypatch.setattr(nutrition, "_chat_json", fake_chat)
    out = await nutrition.enrich_missing(
        [
            {"normalized_name": "buttermilk", "unit": "ml", "name": "Buttermilk"},
            {"normalized_name": "roti", "unit": "piece", "name": "Roti"},
        ]
    )

    per_ml = out[("buttermilk", "ml")]
    assert per_ml.calories == 0.4  # not rounded away to 0.0
    # A 250 ml glass lands in a sane place, not the 75 g of protein we saw raw.
    assert per_ml.scaled(250).protein_g == 8.8
    assert out[("roti", "piece")].calories == 104  # per-piece untouched


async def test_unit_mismatch_falls_back_to_name(monkeypatch):
    async def fake_chat(system, user, schema):
        return {
            "foods": [
                {"normalized_name": "curd", "unit": "bowl", "calories": 120,
                 "protein_g": 8, "carbs_g": 9, "fat_g": 5, "fiber_g": 0,
                 "sugar_g": 9, "sodium_mg": 60}
            ]
        }

    monkeypatch.setattr(nutrition, "_chat_json", fake_chat)
    # asked for a cup, model answered with a bowl -- better to use it than to
    # save a zero-calorie food
    out = await nutrition.enrich_missing(
        [{"normalized_name": "curd", "unit": "cup", "name": "Curd"}]
    )
    assert out[("curd", "cup")].calories == 120


def test_implausible_macros_are_flagged():
    # the real bug: 100 kcal but 75 g of protein
    assert Nutrition(calories=100, protein_g=75).implausible() is not None
    # a normal roti passes
    assert Nutrition(
        calories=104, protein_g=3.1, carbs_g=18, fat_g=2.4
    ).implausible() is None
    # no calories logged -> nothing to cross-check
    assert Nutrition().implausible() is None
