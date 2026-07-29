# app/infrastructure/observability/langsmith_client.py (new)
from __future__ import annotations

from functools import lru_cache

from langsmith import Client

from app.core.config import get_settings


@lru_cache
def get_langsmith_client() -> Client:
    settings = get_settings()
    return Client(api_key=settings.LANGSMITH_API_KEY)