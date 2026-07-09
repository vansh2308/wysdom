from typing import AsyncIterator, Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_session_factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """
    Request-scoped session pulled from the shared singleton pool.
    Rolls back on unhandled exceptions; commit is the caller's responsibility
    (repository / unit-of-work), not this dependency's.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# Convenience alias for route signatures
DbSession = Annotated[AsyncSession, Depends(get_db_session)]