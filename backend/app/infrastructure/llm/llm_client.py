
from __future__ import annotations

from functools import lru_cache

from anthropic import AsyncAnthropic

from app.core.config import get_settings

from openai import AsyncOpenAI


@lru_cache
def get_anthropic_client() -> AsyncAnthropic:
    return AsyncAnthropic(api_key=get_settings().ANTHROPIC_API_KEY)


@lru_cache
def get_openai_client() -> AsyncOpenAI:
    settings = get_settings()
    return AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.OPENAI_API_KEY
    )
