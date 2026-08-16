import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings
from .models import Base

logger = logging.getLogger(__name__)
settings = get_settings()

db_url = settings.database_url
if db_url.startswith("sqlite:///"):
    db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)

engine = create_async_engine(db_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _add_missing_columns(conn)


async def _add_missing_columns(conn) -> None:
    """Poor man's migration. `create_all` never alters an existing table, so a
    new column would be invisible to a database that already holds your food
    log. SQLite can add nullable columns cheaply, so do exactly that."""
    for table in Base.metadata.sorted_tables:
        result = await conn.exec_driver_sql(f"PRAGMA table_info({table.name})")
        existing = {row[1] for row in result.fetchall()}
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
