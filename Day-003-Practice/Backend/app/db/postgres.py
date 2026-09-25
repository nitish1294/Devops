import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

log = logging.getLogger("hrms.db")

engine = create_async_engine(
    settings.postgres_dsn,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_postgres() -> None:
    """Verify the schema is present and current.

    Alembic owns the schema. Creating tables from the models at startup would
    quietly diverge from the migration history the moment a model changed, and
    the divergence would only surface on the next deployment. So this checks
    rather than creates, and says exactly what to run if the check fails.

    AUTO_CREATE_SCHEMA=true restores create_all for a throwaway database, which
    is convenient for a test run and wrong for anything you care about.
    """
    from sqlalchemy import inspect

    from app.models import registry  # noqa: F401  (imports every model)
    from app.models.base import Base

    async with engine.begin() as conn:
        if settings.AUTO_CREATE_SCHEMA:
            await conn.run_sync(Base.metadata.create_all)
            log.warning(
                "created tables directly from the models; "
                "set AUTO_CREATE_SCHEMA=false and use Alembic for a real database"
            )
            return

        tables = await conn.run_sync(lambda c: inspect(c).get_table_names())

    if "alembic_version" not in tables:
        raise RuntimeError(
            "The database has no schema. Run `alembic upgrade head` from the "
            "backend directory before starting the app."
        )

    missing = sorted(set(Base.metadata.tables) - set(tables))
    if missing:
        raise RuntimeError(
            f"The database is behind the code — missing {', '.join(missing)}. "
            "Run `alembic upgrade head`."
        )
    log.info("schema verified", extra={"tables": len(tables)})
