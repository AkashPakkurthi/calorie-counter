import logging
from collections.abc import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings
from .models import Base

logger = logging.getLogger(__name__)
settings = get_settings()

def async_url(url: str) -> str:
    """Point whatever URL we were handed at an async driver.

    Hosts hand out `postgres://` or `postgresql://`; SQLAlchemy needs the
    driver spelled out, and we need the async one either way.
    """
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    for prefix in ("postgresql+asyncpg://", "sqlite+aiosqlite://"):
        if url.startswith(prefix):
            return url
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+asyncpg://" + url[len(prefix) :]
    return url


# libpq spellings that hosts append by default but asyncpg refuses to accept.
LIBPQ_ONLY_PARAMS = ("sslmode", "channel_binding", "options")


def build_engine_args(raw_url: str) -> tuple[str, dict]:
    """Return the URL and engine kwargs for whatever database we were given.

    Serverless Postgres (Neon) needs three accommodations: its pooler chokes
    on asyncpg's prepared-statement cache, it drops idle connections, and it
    requires TLS. TLS mode comes from the URL's `sslmode` when present --
    hardcoding "require" would break a provider that serves plaintext over a
    private network. Default is "prefer": encrypt when offered, still connect
    when not.
    """
    url = async_url(raw_url)
    if not url.startswith("postgresql"):
        return url, {"echo": False}

    parts = urlparse(url)
    params = dict(parse_qsl(parts.query))
    kept = [(k, v) for k, v in parse_qsl(parts.query) if k not in LIBPQ_ONLY_PARAMS]
    url = urlunparse(parts._replace(query=urlencode(kept)))

    return url, {
        "echo": False,
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "connect_args": {
            "statement_cache_size": 0,
            "ssl": params.get("sslmode", "prefer"),
        },
    }


db_url, _engine_args = build_engine_args(settings.database_url)
engine = create_async_engine(db_url, **_engine_args)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _add_missing_columns(conn)


async def _existing_columns(conn, table_name: str) -> set[str]:
    if conn.dialect.name == "sqlite":
        result = await conn.exec_driver_sql(f"PRAGMA table_info({table_name})")
        return {row[1] for row in result.fetchall()}
    result = await conn.exec_driver_sql(
        "SELECT column_name FROM information_schema.columns "
        f"WHERE table_name = '{table_name}'"
    )
    return {row[0] for row in result.fetchall()}


async def _add_missing_columns(conn) -> None:
    """Poor man's migration. `create_all` never alters an existing table, so a
    new column would be invisible to a database that already holds your food
    log. Adding a nullable column is cheap on both SQLite and Postgres."""
    for table in Base.metadata.sorted_tables:
        existing = await _existing_columns(conn, table.name)
        if not existing:
            continue
        for column in table.columns:
            if column.name in existing or column.primary_key:
                continue
            col_type = column.type.compile(conn.dialect)
            logger.info("adding missing column %s.%s", table.name, column.name)
            await conn.exec_driver_sql(
                f"ALTER TABLE {table.name} ADD COLUMN {column.name} {col_type}"
            )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
