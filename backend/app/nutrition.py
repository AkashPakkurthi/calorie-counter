"""Free text -> resolved foods with full macros.

Two GPT passes, both cheap, and a SQLite-backed per-unit cache in between:

  1. parse   -- always runs; splits the text into {name, quantity, unit}
  2. lookup  -- anything already in `food_cache` is resolved for free
  3. enrich  -- one batched call for the leftovers, storing PER-ONE-UNIT
                nutrition so the next time that food is free too
"""

import json
import logging
from datetime import UTC, datetime

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import FoodCache
from .schemas import Nutrition, ResolvedItem, Unit
from .utils import normalize

logger = logging.getLogger(__name__)
settings = get_settings()

_client: AsyncOpenAI | None = None

UNITS = ["piece", "g", "ml", "bowl", "cup", "tbsp", "slice", "serving"]

PROFILE = "a 26 year old Indian male, 178cm, ~86kg, moderately active"


class NutritionError(RuntimeError):
    """Raised when GPT cannot be reached -- surfaced to the UI, never saved."""


def get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        if not settings.openai_api_key:
            raise NutritionError(
                "No API key configured. Set OPENAI_API_KEY in your environment "
                "(or .env when running locally) and restart."
            )
        kwargs = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            kwargs["base_url"] = settings.openai_base_url
        _client = AsyncOpenAI(**kwargs)
    return _client


PARSE_SCHEMA = {
    "name": "parsed_meal",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["name", "normalized_name", "quantity", "unit"],
                    "properties": {
                        "name": {"type": "string"},
                        "normalized_name": {"type": "string"},
                        "quantity": {"type": "number"},
                        "unit": {"type": "string", "enum": UNITS},
                    },
                },
            }
        },
    },
}

NUTRITION_PROPS = {
    "calories": {"type": "number"},
    "protein_g": {"type": "number"},
    "carbs_g": {"type": "number"},
    "fat_g": {"type": "number"},
    "fiber_g": {"type": "number"},
    "sugar_g": {"type": "number"},
    "sodium_mg": {"type": "number"},
}

ENRICH_SCHEMA = {
    "name": "food_nutrition",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["foods"],
        "properties": {
            "foods": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["normalized_name", "unit", *NUTRITION_PROPS],
                    "properties": {
                        "normalized_name": {"type": "string"},
                        "unit": {"type": "string", "enum": UNITS},
                        **NUTRITION_PROPS,
                    },
                },
            }
        },
    },
}

PARSE_PROMPT = f"""You split a meal description into individual foods for {PROFILE}.

Rules:
- One entry per distinct food. Split combined dishes only when they are clearly separate items.
- `quantity` + `unit`: if the user gave a weight or count, use it exactly.
  If they did NOT, YOU decide a realistic portion for {PROFILE} eating a normal
  home meal (e.g. "dal" -> 1 bowl, "rice" -> 200 g, "curd" -> 1 cup).
  Never return 0 and never ask for clarification.
- Prefer natural units: countable foods -> "piece"/"slice", curries/dals -> "bowl",
  liquids -> "ml", loose solids -> "g".
- `normalized_name`: lowercase, singular, no quantity words ("3 rotis" -> "roti",
  "Paneer Butter Masala" -> "paneer butter masala").
- `name`: a clean human label, title-ish case."""

# Per-gram / per-ml figures are so small that models fumble them (0.03 g of
# protein per ml, etc). Ask for the familiar per-100 basis and divide it down.
BASIS = {"g": 100, "ml": 100}

ENRICH_PROMPT = f"""You are a nutrition database for Indian and common Western foods.

For EACH food given, return nutrition on this basis:
- unit "g"  -> values per 100 GRAMS
- unit "ml" -> values per 100 MILLILITRES
- every other unit -> values for exactly ONE of that unit (one piece, one bowl,
  one cup, one slice, one serving) -- NOT for the whole portion.

Assume typical home-cooked preparation for {PROFILE}.
A "bowl" is ~200 g, a "cup" ~240 ml, a "serving" is one normal portion.
Keep the numbers internally consistent: protein and carbs are ~4 kcal/g and fat
~9 kcal/g, so they must roughly add up to the calories you give.
Return your best numeric estimate for every field -- never null, never zero unless
genuinely zero. Echo `normalized_name` and `unit` back exactly as given."""


"""Not every OpenAI-compatible provider supports strict `json_schema`
(Groq only offers it on some models, Ollama on none). We try it first, and on
a rejection fall back to plain JSON mode with the schema written into the
prompt -- then cache the answer so we stop paying for the failed attempt."""
_json_schema_supported: bool | None = None


def _unsupported_schema_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "response_format" in msg or "json_schema" in msg


def _extract_json(text: str) -> dict:
    """JSON mode is not strict, so tolerate prose or a ```json fence."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1].removeprefix("json").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


async def _call(system: str, user: str, schema: dict, strict: bool) -> str:
    response_format = (
        {"type": "json_schema", "json_schema": schema} if strict else {"type": "json_object"}
    )
    if not strict:
        # The model no longer gets the schema for free -- spell it out.
        system = (
            f"{system}\n\nReply with JSON only -- no prose, no markdown fence -- "
            f"matching exactly this JSON Schema:\n{json.dumps(schema['schema'])}"
        )
    response = await get_client().chat.completions.create(
        model=settings.openai_model,
        temperature=0,
        response_format=response_format,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return response.choices[0].message.content


async def _chat_json(system: str, user: str, schema: dict) -> dict:
    global _json_schema_supported
    try:
        if _json_schema_supported is not False:
            try:
                content = await _call(system, user, schema, strict=True)
                _json_schema_supported = True
                return _extract_json(content)
            except Exception as exc:  # noqa: BLE001
                if not _unsupported_schema_error(exc):
                    raise
                logger.info(
                    "%s does not support json_schema; using JSON mode instead",
                    settings.openai_model,
                )
                _json_schema_supported = False

        return _extract_json(await _call(system, user, schema, strict=False))
    except NutritionError:
        raise
    except Exception as exc:  # noqa: BLE001 - surfaced to the UI as a clean error
        logger.warning("Nutrition model call failed: %s", exc)
        raise NutritionError(f"Could not reach the nutrition model: {exc}") from exc


async def parse_text(text: str, meal_type: str) -> list[dict]:
    data = await _chat_json(
        PARSE_PROMPT, f"Meal: {meal_type}\nWhat I ate: {text}", PARSE_SCHEMA
    )
    items = []
    for raw in data.get("items", []):
        qty = float(raw.get("quantity") or 0)
        items.append(
            {
                "name": (raw.get("name") or "").strip() or "Food",
                "normalized_name": normalize(raw.get("normalized_name") or raw.get("name", "")),
                "quantity": qty if qty > 0 else 1.0,
                "unit": raw.get("unit") if raw.get("unit") in UNITS else "serving",
            }
        )
    return [i for i in items if i["normalized_name"]]


async def lookup_cache(
    db: AsyncSession, user_id: int, normalized_name: str, unit: str
) -> FoodCache | None:
    result = await db.execute(
        select(FoodCache).where(
            FoodCache.user_id == user_id,
            FoodCache.normalized_name == normalized_name,
            FoodCache.unit == unit,
        )
    )
    return result.scalar_one_or_none()


async def upsert_cache(
    db: AsyncSession,
    user_id: int,
    normalized_name: str,
    display_name: str,
    unit: str,
    per_unit: Nutrition,
    bump: bool = False,
) -> FoodCache:
    row = await lookup_cache(db, user_id, normalized_name, unit)
    if row is None:
        row = FoodCache(
            user_id=user_id,
            normalized_name=normalized_name,
            display_name=display_name,
            unit=unit,
            hit_count=0,
        )
        db.add(row)
    for field, value in per_unit.model_dump().items():
        setattr(row, field, value)
    row.display_name = display_name or row.display_name
    row.last_used_at = datetime.now(UTC)
    if bump:
        row.hit_count = (row.hit_count or 0) + 1
    await db.flush()
    return row


def _to_nutrition(obj) -> Nutrition:
    return Nutrition(
        calories=obj.calories or 0,
        protein_g=obj.protein_g or 0,
        carbs_g=obj.carbs_g or 0,
        fat_g=obj.fat_g or 0,
        fiber_g=obj.fiber_g or 0,
        sugar_g=obj.sugar_g or 0,
        sodium_mg=obj.sodium_mg or 0,
    )


async def enrich_missing(items: list[dict]) -> dict[tuple[str, str], Nutrition]:
    if not items:
        return {}
    payload = json.dumps(
        [{"normalized_name": i["normalized_name"], "unit": i["unit"]} for i in items]
    )
    data = await _chat_json(ENRICH_PROMPT, f"Foods: {payload}", ENRICH_SCHEMA)

    out: dict[tuple[str, str], Nutrition] = {}
    by_name: dict[str, Nutrition] = {}
    for food in data.get("foods", []):
        name = normalize(food.get("normalized_name", ""))
        unit = food.get("unit", "serving")
        values = Nutrition(**{k: float(food.get(k) or 0) for k in NUTRITION_PROPS})
        values = values.scaled(1 / BASIS.get(unit, 1), 4)  # per-100 -> per-unit
        out[(name, unit)] = values
        by_name[name] = values

    # In JSON mode the unit enum isn't enforced, so a model may echo back
    # "pieces" or "grams". Fall back to matching on the food name alone rather
    # than silently returning a zero-calorie item.
    for item in items:
        key = (item["normalized_name"], item["unit"])
        if key not in out and item["normalized_name"] in by_name:
            out[key] = by_name[item["normalized_name"]]
    return out


async def resolve_meal(
    db: AsyncSession, user_id: int, text: str, meal_type: str
) -> list[ResolvedItem]:
    """Full pipeline. Returns absolute (quantity-multiplied) nutrition.

    Nothing is written to meal history here -- only the food cache is warmed.
    """
    parsed = await parse_text(text, meal_type)

    cached: dict[tuple[str, str], Nutrition] = {}
    missing: list[dict] = []
    for item in parsed:
        key = (item["normalized_name"], item["unit"])
        if key in cached:
            continue
        row = await lookup_cache(db, user_id, *key)
        if row is not None:
            cached[key] = _to_nutrition(row)
        elif key not in {(m["normalized_name"], m["unit"]) for m in missing}:
            missing.append(item)

    enriched = await enrich_missing(missing)
    for item in missing:
        key = (item["normalized_name"], item["unit"])
        per_unit = enriched.get(key, Nutrition())
        await upsert_cache(db, user_id, key[0], item["name"], key[1], per_unit)
    await db.commit()

    resolved: list[ResolvedItem] = []
    for item in parsed:
        key = (item["normalized_name"], item["unit"])
        from_cache = key in cached
        per_unit = cached.get(key) or enriched.get(key, Nutrition())
        totals = per_unit.scaled(item["quantity"])
        resolved.append(
            ResolvedItem(
                name=item["name"],
                normalized_name=key[0],
                quantity=item["quantity"],
                unit=key[1],  # type: ignore[arg-type]
                from_cache=from_cache,
                **totals.model_dump(),
            )
        )
    return resolved


def per_unit_from_absolute(item: ResolvedItem) -> Nutrition:
    """Invert the multiplication so an edited item teaches the cache."""
    qty = item.quantity or 1
    return Nutrition(**item.model_dump(include=set(Nutrition.model_fields))).scaled(1 / qty, 4)


def unit_is_valid(unit: str) -> bool:
    return unit in UNITS


__all__ = [
    "NutritionError",
    "Unit",
    "resolve_meal",
    "upsert_cache",
    "lookup_cache",
    "per_unit_from_absolute",
    "unit_is_valid",
]
