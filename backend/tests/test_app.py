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
from backend.app.models import Base, User, UserSettings, WeightLog  # noqa: E402
from backend.app.nutrition import per_unit_from_absolute, upsert_cache  # noqa: E402
from backend.app.schemas import Nutrition, ResolvedItem  # noqa: E402
from backend.app.services import build_day, day_summaries, save_meal  # noqa: E402
from backend.app.utils import normalize, today_str  # noqa: E402

pytestmark = pytest.mark.asyncio


ME = 1       # the signed-in user in these tests
OTHER = 2    # a second account, used to prove data does not leak


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add_all(
            [
                User(id=ME, email="me@example.com", password_hash="x"),
                User(id=OTHER, email="other@example.com", password_hash="x"),
                UserSettings(user_id=ME, weight_kg=86.0),
                UserSettings(user_id=OTHER, weight_kg=60.0),
            ]
        )
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
    assert await weight_for_date(db, ME, "2026-01-01") == 86.0


async def test_weight_uses_entry_in_effect_on_that_date(db):
    db.add_all(
        [
            WeightLog(user_id=ME, date="2026-01-04", weight_kg=86.0),
            WeightLog(user_id=ME, date="2026-02-01", weight_kg=82.0),
        ]
    )
    await db.commit()

    # A day between weigh-ins uses the earlier one...
    assert await weight_for_date(db, ME, "2026-01-20") == 86.0
    # ...a day after the newer one uses the newer weight...
    assert await weight_for_date(db, ME, "2026-02-10") == 82.0
    # ...and a day before any weigh-in falls back to the profile, so a new
    # weigh-in never retroactively rewrites older days.
    assert await weight_for_date(db, ME, "2025-12-25") == 86.0


async def test_old_day_burn_unchanged_by_new_weigh_in(db):
    db.add(WeightLog(user_id=ME, date="2026-01-04", weight_kg=86.0))
    await db.commit()
    before = total_burn(60, 0, await weight_for_date(db, ME, "2026-01-10"))

    db.add(WeightLog(user_id=ME, date="2026-06-01", weight_kg=78.0))
    await db.commit()
    after = total_burn(60, 0, await weight_for_date(db, ME, "2026-01-10"))

    assert before == after
    assert total_burn(60, 0, await weight_for_date(db, ME, "2026-06-05")) < before


# --- cache ---------------------------------------------------------------


async def test_saving_a_meal_teaches_the_cache(db):
    date = today_str()
    await save_meal(db, ME, date, "lunch", "3 rotis", [item("Roti", qty=3, calories=300, protein_g=9)])

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
    await upsert_cache(db, ME, "roti", "Roti", "piece", Nutrition(calories=100), bump=True)
    row = await upsert_cache(db, ME, "roti", "Roti", "piece", Nutrition(calories=120), bump=True)
    await db.commit()
    assert row.calories == 120  # a correction sticks
    assert row.hit_count == 2


# --- day aggregation -----------------------------------------------------


async def test_day_totals_and_net_calories(db):
    date = today_str()
    await save_meal(db, ME, date, "breakfast", "", [item("Idli", qty=2, calories=140, protein_g=4)])
    await save_meal(db, ME, date, "lunch", "", [item("Rice", qty=1, unit="bowl", calories=260, protein_g=5)])

    from backend.app.models import ActivityLog

    db.add(ActivityLog(user_id=ME, date=date, walking_min=60, tt_min=0))
    await db.commit()

    day = await build_day(db, ME, date)
    assert day.totals.calories == 400
    assert day.totals.protein_g == 9
    assert day.activity.calories_burned == 301.0
    assert day.net_calories == 99.0
    assert len(day.meals["breakfast"]) == 1
    assert day.targets.daily_calories == 2500


async def test_empty_day_is_zeroed_not_an_error(db):
    day = await build_day(db, ME, "2026-03-01")
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


# --- goal -> daily targets ------------------------------------------------

from backend.app.plan import build_plan  # noqa: E402


def plan_for(target, date, weight=86.0, start=None, today="2026-08-16"):
    return build_plan(
        current_weight=weight, height_cm=178, age=26, sex="male",
        target_weight=target, target_date=date, start_weight=start, today=today,
    )


def test_no_goal_means_maintenance():
    p = plan_for(None, None)
    assert p.daily_delta == 0
    assert p.recommended["daily_calories"] == p.maintenance
    assert p.warnings == []


def test_maintenance_excludes_logged_exercise():
    # BMR 1848 x 1.2 sedentary -- NOT x1.375, which would double-count the
    # walking and table tennis that are logged as burn.
    assert plan_for(None, None).maintenance == 2217


def test_reasonable_goal_produces_a_deficit():
    p = plan_for(82.0, "2026-10-25")  # 4 kg in 70 days
    assert p.kg_to_go == 4.0
    assert p.days_left == 70
    assert p.weekly_rate == 0.4
    assert p.daily_delta == 440
    assert p.recommended["daily_calories"] == p.maintenance - 440
    assert p.achievable and not p.warnings


def test_crash_diet_is_capped_at_a_floor_not_obeyed():
    p = plan_for(76.0, "2026-09-15")  # 10 kg in 30 days
    assert not p.achievable
    assert p.recommended["daily_calories"] >= 1500
    assert any("floor" in w for w in p.warnings)
    assert any("kg/week" in w for w in p.warnings)


def test_bulk_surplus_is_capped():
    p = plan_for(92.0, "2026-09-15")
    assert not p.achievable
    assert p.recommended["daily_calories"] <= p.maintenance + 500
    assert any("surplus" in w for w in p.warnings)


def test_past_date_is_rejected_gracefully():
    p = plan_for(80.0, "2026-01-01")
    assert not p.achievable
    assert p.days_left <= 0
    assert any("passed" in w for w in p.warnings)
    assert p.recommended["daily_calories"] == p.maintenance  # falls back safely


def test_progress_measured_from_the_weight_when_goal_was_set():
    p = plan_for(78.0, "2026-12-31", weight=84.0, start=86.0)
    assert p.start_weight == 86.0
    assert p.progress_pct == 25.0  # 2 kg of the 8 kg gap
    # and it never runs past the ends
    assert plan_for(78.0, "2026-12-31", weight=70.0, start=86.0).progress_pct == 100.0
    assert plan_for(78.0, "2026-12-31", weight=90.0, start=86.0).progress_pct == 0.0


def test_cut_protein_is_high_and_macros_reconstruct_calories():
    r = plan_for(82.0, "2026-10-25").recommended
    assert r["protein_g"] == 172  # 2 g/kg to protect muscle
    derived = 4 * r["protein_g"] + 4 * r["carbs_g"] + 9 * r["fat_g"]
    assert abs(derived - r["daily_calories"]) < 30


# --- database URL handling (SQLite locally, Postgres when hosted) ----------

from backend.app.db import build_engine_args  # noqa: E402


def test_sqlite_url_gets_the_async_driver():
    url, kw = build_engine_args("sqlite:///./calories.db")
    assert url == "sqlite+aiosqlite:///./calories.db"
    assert "connect_args" not in kw  # no Postgres pooling knobs


def test_neon_url_is_made_asyncpg_safe():
    url, kw = build_engine_args(
        "postgres://u:p@ep-x.neon.tech/neondb?sslmode=require&channel_binding=require"
    )
    # asyncpg needs its own driver name and rejects the libpq-only params
    assert url == "postgresql+asyncpg://u:p@ep-x.neon.tech/neondb"
    assert kw["connect_args"]["ssl"] == "require"
    # Neon's pooler cannot handle asyncpg's prepared statements
    assert kw["connect_args"]["statement_cache_size"] == 0
    assert kw["pool_pre_ping"] is True


def test_plaintext_postgres_still_connects():
    # A provider on a private network may not offer TLS at all; "prefer" uses
    # it when available instead of refusing to connect.
    _, kw = build_engine_args("postgresql://postgres:pw@10.0.0.5:5432/calories")
    assert kw["connect_args"]["ssl"] == "prefer"


# --- accounts: passwords, invite gate, and isolation between users --------

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from backend.app import auth as auth_mod  # noqa: E402
from backend.app.models import ActivityLog as AL  # noqa: E402


def test_password_hashing_roundtrip():
    hashed = auth_mod.hash_password("correct horse battery")
    assert hashed != "correct horse battery"  # never stored in the clear
    assert auth_mod.verify_password("correct horse battery", hashed)
    assert not auth_mod.verify_password("wrong password", hashed)


def test_absurdly_long_password_is_rejected_not_truncated():
    # bcrypt silently ignores anything past 72 bytes, which would make
    # "password" + 200 chars equivalent to a different long password.
    with pytest.raises(HTTPException):
        auth_mod.hash_password("x" * 200)


def test_emails_are_matched_case_insensitively():
    assert auth_mod.normalize_email("  Me@Example.COM ") == "me@example.com"


def test_invite_gate(monkeypatch):
    monkeypatch.setattr(auth_mod.settings, "invite_code", "letmein")
    auth_mod.check_invite("letmein")  # correct code passes
    for bad in (None, "", "nope", "LETMEIN"):
        with pytest.raises(HTTPException):
            auth_mod.check_invite(bad)

    monkeypatch.setattr(auth_mod.settings, "invite_code", "")
    auth_mod.check_invite(None)  # blank config disables the gate entirely


def test_session_cookie_is_signed_and_tamper_evident():
    token = auth_mod.serializer.dumps({"uid": 7})
    assert auth_mod.serializer.loads(token) == {"uid": 7}
    forged = auth_mod.URLSafeTimedSerializer("attacker-key", salt=auth_mod.SALT).dumps(
        {"uid": 1}
    )
    with pytest.raises(Exception):
        auth_mod.serializer.loads(forged)


async def test_one_users_meals_never_appear_in_anothers_day(db):
    date = today_str()
    await save_meal(db, ME, date, "lunch", "", [item("Roti", qty=3, calories=300)])
    await save_meal(db, OTHER, date, "lunch", "", [item("Pizza", qty=1, calories=900)])

    mine = await build_day(db, ME, date)
    theirs = await build_day(db, OTHER, date)
    assert mine.totals.calories == 300
    assert theirs.totals.calories == 900
    assert [i.name for m in mine.meals["lunch"] for i in m.items] == ["Roti"]


async def test_burn_uses_each_users_own_weight(db):
    date = today_str()
    db.add_all(
        [
            AL(user_id=ME, date=date, walking_min=60, tt_min=0),
            AL(user_id=OTHER, date=date, walking_min=60, tt_min=0),
        ]
    )
    await db.commit()

    mine = await build_day(db, ME, date)
    theirs = await build_day(db, OTHER, date)
    assert mine.activity.calories_burned == 301.0  # 86 kg
    assert theirs.activity.calories_burned == 210.0  # 60 kg
    assert mine.activity.calories_burned != theirs.activity.calories_burned


async def test_weight_log_is_per_user(db):
    db.add_all(
        [
            WeightLog(user_id=ME, date="2026-08-01", weight_kg=84.0),
            WeightLog(user_id=OTHER, date="2026-08-01", weight_kg=58.0),
        ]
    )
    await db.commit()
    assert await weight_for_date(db, ME, "2026-08-10") == 84.0
    assert await weight_for_date(db, OTHER, "2026-08-10") == 58.0


async def test_history_is_scoped(db):
    await save_meal(db, OTHER, "2026-08-10", "dinner", "", [item("Pasta", calories=700)])
    mine = await day_summaries(db, ME, "2026-08-01", "2026-08-31")
    assert mine == []  # their day must not show up in my history


async def test_targets_are_per_user(db):
    from backend.app.services import get_settings_row

    row = await get_settings_row(db, ME)
    row.daily_calories = 1800
    await db.commit()

    assert (await build_day(db, ME, today_str())).targets.daily_calories == 1800
    assert (await build_day(db, OTHER, today_str())).targets.daily_calories == 2500


async def test_food_cache_and_picker_are_per_user(db):
    from sqlalchemy import select

    from backend.app.models import FoodCache

    date = today_str()
    await save_meal(db, ME, date, "lunch", "", [item("Roti", qty=3, calories=300)])
    await save_meal(db, OTHER, date, "lunch", "", [item("Pizza", qty=1, calories=900)])

    mine = (await db.execute(select(FoodCache).where(FoodCache.user_id == ME))).scalars()
    assert [f.normalized_name for f in mine] == ["roti"]  # not "pizza"

    # the same food learned by two people is stored twice, so a correction by
    # one of them cannot change the other's numbers
    await save_meal(db, OTHER, date, "dinner", "", [item("Roti", qty=1, calories=150)])
    rows = (
        await db.execute(select(FoodCache).where(FoodCache.normalized_name == "roti"))
    ).scalars().all()
    assert len(rows) == 2
    assert {r.user_id: r.calories for r in rows} == {ME: 100, OTHER: 150}


def test_session_cookie_is_secure_only_over_https():
    """A Secure cookie is dropped by the browser on plain HTTP, which looks
    like a silently broken login -- so the flag follows the actual scheme."""
    from unittest.mock import Mock

    from fastapi import Response

    def cookie_for(scheme, forwarded=None):
        request = Mock()
        request.url.scheme = scheme
        request.headers = {"x-forwarded-proto": forwarded} if forwarded else {}
        response = Response()
        auth_mod.set_session(request, response, user_id=1)
        return response.headers["set-cookie"]

    assert "Secure" not in cookie_for("http")          # local development
    assert "Secure" in cookie_for("https")             # real deployment
    # behind a proxy the app sees http, so trust the forwarded scheme
    assert "Secure" in cookie_for("http", forwarded="https")
    assert "HttpOnly" in cookie_for("http")            # never readable from JS


async def test_requests_get_503_while_the_database_is_still_waking(monkeypatch):
    """Neon takes tens of seconds to wake. Requests in that window should be
    told to retry, not blow up -- and must never hang forever."""
    import asyncio

    from fastapi import HTTPException

    from backend.app import db as db_mod

    monkeypatch.setattr(db_mod, "schema_ready", asyncio.Event())  # not set
    monkeypatch.setattr(db_mod, "WAIT_FOR_SCHEMA_SECONDS", 0.05)

    with pytest.raises(HTTPException) as caught:
        async for _ in db_mod.get_db():
            pass
    assert caught.value.status_code == 503
    assert "waking up" in caught.value.detail


async def test_startup_retries_a_sleeping_database(monkeypatch):
    """A Neon instance that is still waking refuses the first connections;
    startup must keep trying rather than leaving the app dead."""
    import asyncio

    from backend.app import db as db_mod

    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("connection refused")

    real_sleep = asyncio.sleep  # keep a handle before patching, or it recurses

    async def no_wait(_seconds):
        await real_sleep(0)

    monkeypatch.setattr(db_mod, "init_db", flaky)
    monkeypatch.setattr(db_mod, "schema_ready", asyncio.Event())
    monkeypatch.setattr(db_mod.asyncio, "sleep", no_wait)

    await db_mod.init_db_background()
    assert calls["n"] == 3
    assert db_mod.schema_ready.is_set()  # recovered instead of giving up
