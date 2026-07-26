# app/infrastructure/conversations/namer.py
from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.knowledge.embedding_client import get_openai_client

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Generate a short, descriptive conversation title (3-6 words, \
no trailing punctuation, no quotation marks) summarizing what the user is asking \
about in their first message."""


class _NameSuggestion(BaseModel):
    name: str = Field(..., max_length=80)


class LlmConversationNamer:
    """ConversationNamerPort adapter. Deliberately uses a cheap/fast model —
    this runs once per conversation on a handful of tokens, no reason to
    spend planner/synthesizer-tier budget on it."""

    async def predict_name(self, first_message: str) -> str:
        settings = get_settings()
        client = get_openai_client()
        try:
            response = await client.responses.parse(
                model=settings.CONVERSATION_NAMER_MODEL,
                input=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": first_message[:2000]},
                ],
                text_format=_NameSuggestion,
            )
            suggestion = response.output_parsed
            if suggestion and suggestion.name.strip():
                return suggestion.name.strip()
            raise ValueError("empty name suggestion")
        except Exception as exc:
            logger.warning("Conversation naming failed, falling back to truncation: %s", exc)
            return self._fallback_name(first_message)

    @staticmethod
    def _fallback_name(first_message: str) -> str:
        title = " ".join(first_message.strip().split()[:6])
        return title[:80] if title else "New conversation"