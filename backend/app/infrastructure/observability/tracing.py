
from __future__ import annotations

import logging
import os

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def init_langsmith_tracing() -> None:
    """
    Sets the env vars LangSmith's SDK and LangGraph's native tracing hooks
    both read. Once set, every LangGraph node execution is auto-traced as
    a run with zero per-node code changes — this call is the entire
    integration for node-level tracing.
    """
    settings = get_settings()
    if not settings.LANGSMITH_TRACING_ENABLED or not settings.LANGSMITH_API_KEY:
        logger.warning("LangSmith tracing disabled (no API key or explicitly turned off)")
        return
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
    logger.info("LangSmith tracing enabled (project=%s)", settings.LANGSMITH_PROJECT)