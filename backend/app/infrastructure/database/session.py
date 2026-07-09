from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

@lru_cache
def get_engine() -> AsyncEngine:
    """
    Process-wide singleton engine + connection pool.

    lru_cache guarantees the body runs once per process no matter how many
    times FastAPI resolves a dependency chain that touches it.
    """
    settings = get_settings()
    return create_async_engine(
        str(settings.db_url),
        echo=settings.db_echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        pool_pre_ping=True,
        connect_args = {"ssl": True}
    )


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def dispose_engine() -> None:
    """Call on app shutdown for a graceful pool teardown."""
    await get_engine().dispose()