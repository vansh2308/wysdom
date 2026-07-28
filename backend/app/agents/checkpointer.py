from __future__ import annotations

import logging

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_checkpointer_ctx = None
_checkpointer: AsyncPostgresSaver | None = None


async def init_checkpointer() -> AsyncPostgresSaver:
    """
    Opens one long-lived AsyncPostgresSaver for the app's lifetime and runs
    its one-time table setup (checkpoints, checkpoint_blobs,
    checkpoint_writes, checkpoint_migrations — entirely managed by
    langgraph-checkpoint-postgres, not hand-designed in our schema).

    Uses the direct (non-pooler) Neon connection — same reasoning as
    Alembic: this library manages its own connection/prepared-statement
    lifecycle, which doesn't play well with pgbouncer transaction pooling.
    """
    global _checkpointer_ctx, _checkpointer
    settings = get_settings()
    _checkpointer_ctx = AsyncPostgresSaver.from_conn_string(str(settings.MIGRATIONS_DATABASE_URL))
    _checkpointer = await _checkpointer_ctx.__aenter__()
    await _checkpointer.setup()
    logger.info("LangGraph Postgres checkpointer initialized")
    return _checkpointer


async def close_checkpointer() -> None:
    global _checkpointer_ctx, _checkpointer
    if _checkpointer_ctx is not None:
        await _checkpointer_ctx.__aexit__(None, None, None)
        _checkpointer_ctx = None
        _checkpointer = None


def get_checkpointer() -> AsyncPostgresSaver:
    if _checkpointer is None:
        raise RuntimeError("Checkpointer not initialized — init_checkpointer() must run during app startup")
    return _checkpointer