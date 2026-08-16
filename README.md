# Calorie Tracker

A single-user calorie and macro tracker. Type what you ate in plain language —
"3 rotis and a bowl of dal" — and GPT works out the portions and the full
nutrition breakdown. Everything it learns is cached, so foods you eat regularly
are logged instantly and for free.

Built for one profile: 26M, 178 cm, 86 kg. No login, no multi-user support.

## What it does

- **Two ways to log food.** *Type it* → GPT parses and estimates → you confirm
  and can correct anything before it saves. *Pick known food* → choose from
  everything the tracker already knows, set a quantity, done — no AI call.
- **Full nutrition.** Calories, protein, carbs, fat, fiber, sugar, sodium, each
  against a target you set yourself.
- **It learns.** Every saved food is stored *per one unit* in `food_cache`. Log
  3 rotis once and it knows what one roti is forever. Corrections stick — fixing
  a value on the Foods page fixes every future meal.
- **Exercise without AI.** Walking and table-tennis minutes, priced by the MET
  formula `kcal = MET × weight × hours` (walking 3.5, TT 4.0).
- **Weight handled honestly.** Log a weigh-in weekly; each day's burn uses the
  weight in effect *on that day*, so a new weigh-in never rewrites old numbers.
- **History.** 7/30/90-day calorie and protein trends, weight trend, weekday
  averages, and any past day in full detail.
- Favourites for one-tap re-adds, and water tracking.

## Running locally

```bash
cp .env.example .env          # then paste your OPENAI_API_KEY into it

python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/python -m uvicorn backend.app.main:app --reload --port 8000

cd frontend && npm install && npm run dev    # http://localhost:5173
```

The Vite dev server proxies `/api` to port 8000. In production FastAPI serves
the built bundle itself, so there is one origin and no CORS.

Tests: `.venv/bin/python -m pytest`

## Deploying free (Render + Neon)

Render's free web service has no disk, so the database lives in Neon's free
Postgres instead. Both are permanently free and neither needs a card.

1. **Neon** — [neon.tech](https://neon.tech) → new project → copy the connection
   string (`postgresql://...?sslmode=require`). 0.5 GB is thousands of meals.
2. **Render** — [render.com](https://render.com) → **New → Web Service** → connect
   the GitHub repo → runtime **Docker** → plan **Free**.
3. Environment variables:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | the Neon connection string |
   | `OPENAI_API_KEY` | your Groq (or OpenAI) key |
   | `OPENAI_BASE_URL` | `https://api.groq.com/openai/v1` for Groq |
   | `OPENAI_MODEL` | `llama-3.3-70b-versatile` for Groq |
   | `APP_TZ` | `Asia/Kolkata` |

4. Deploy. Tables are created on first boot; new columns are added
   automatically on later deploys.

The one catch: a free Render service **sleeps after ~15 minutes idle**, so the
first request after a gap takes up to a minute to wake. Every request after
that is fast. Your data is unaffected — it lives in Neon, not the container.

## Deploying to Railway

1. Push this directory to a GitHub repo.
2. In Railway: **New Project → Deploy from GitHub repo**. `railway.toml` points
   at the Dockerfile, so no build config is needed.
3. Add a **Volume** mounted at `/data`. This is what makes your data survive
   deploys — the SQLite file lives at `/data/calories.db`.
4. Set variables. For OpenAI, `OPENAI_API_KEY` alone is enough. For Groq (or
   any OpenAI-compatible provider) all three are needed:

   | Variable | Groq example |
   |---|---|
   | `OPENAI_API_KEY` | `gsk_...` |
   | `OPENAI_BASE_URL` | `https://api.groq.com/openai/v1` |
   | `OPENAI_MODEL` | `llama-3.3-70b-versatile` |
   | `APP_TZ` | `Asia/Kolkata` (optional, this is the default) |

   Models that lack strict `json_schema` support (most Groq Llama models) are
   handled automatically — the app falls back to JSON mode. `/api/health`
   reports which provider and model it ended up using.
5. Generate a domain. `PORT` is injected by Railway and honored automatically.

`/api/health` is the healthcheck and reports whether the API key was picked up.

The deployed URL is unlisted but public — anyone with the link can log food and
spend your OpenAI credits. Don't share it.

## Layout

```
backend/app/
  main.py        FastAPI app, static SPA mount, health
  config.py      pydantic-settings (OPENAI_API_KEY, DATABASE_URL, APP_TZ)
  db.py          async engine (SQLite or Postgres) + get_db + column check
  models.py      tables
  schemas.py     request/response models
  nutrition.py   GPT parse + enrich passes and the food cache
  exercise.py    MET math and weight_for_date
  services.py    shared day-building / meal-saving helpers
  routers/       meals, days, settings, activity, foods, favourites
frontend/src/
  pages/         Dashboard, History, Settings, Foods
  components/    MealCard (type + pick modes), Rings, SideCards, ui primitives
```

Conventions follow the sibling `ai-search-engine` project: pydantic-settings
with a cached `get_settings()`, async SQLAlchemy + aiosqlite, `lifespan` +
`create_all`, and a lazily constructed OpenAI client. Unlike that project this
one uses `AsyncOpenAI` (so the event loop isn't blocked), Structured Outputs for
typed nutrition, and split `APIRouter` modules.

## Cost

Two small `gpt-4o-mini` calls per *new* food, one per repeat meal, zero for
picks and favourites. Realistically cents per month.
