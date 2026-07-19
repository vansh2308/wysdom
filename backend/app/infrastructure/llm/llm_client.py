
from __future__ import annotations

from functools import lru_cache

from anthropic import AsyncAnthropic

from app.core.config import get_settings


@lru_cache
def get_anthropic_client() -> AsyncAnthropic:
    return AsyncAnthropic(api_key=get_settings().ANTHROPIC_API_KEY)