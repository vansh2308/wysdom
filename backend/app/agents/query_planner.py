# query_planner.py
from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import get_settings

from app.knowledge.models import QueryPlan, SourceType
from app.infrastructure.llm.llm_client import get_openai_client, get_anthropic_client


logger = logging.getLogger(__name__)

# WIP: Just get source_types array instead of pinecone filter 
# WIP: Ig we dont need an LLM here, look for a simpler model 
# Priority: Low 
_SYSTEM_PROMPT = """You are a retrieval query planner for a hybrid search engine over two corpora: "document" chunks (from PDFs/papers) and "repository" chunks (parsed source code). Given a user's query, determine which source types are relevant ("document", "repository", or both).Respond with ONLY a valid Pinecone metadata filter JSON object (raw text, no markdown block, no other text). The JSON must use the following format:{"source_type": {"$in": ["document", "repository"]}}"""


class LlmQueryPlanner:
    """QueryPlannerPort adapter. User-supplied source_types/filter (if any)
    always take precedence over what the LLM decides."""

    async def plan(
        self,
        query: str,
        user_source_types: tuple[SourceType, ...] | None,
        user_filter: dict[str, Any] | None,
    ) -> QueryPlan:
        settings = get_settings()
        client = get_openai_client()
        logger = logging.getLogger(__name__)

        try:
            response = await client.chat.completions.create(
                model = settings.QUERY_PLANNER_MODEL,
                messages = [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": query}
                ],
                extra_body={"reasoning": {"enabled": False}}
            )

            raw_text = response.choices[0].message.content
            planned_filter = json.loads(raw_text)

            # planned_source_types = tuple(SourceType(s) for s in parsed.get("source_types", []))
            # planned_filter = parsed.get("filter", {}) or {}
            # reasoning = resp parsed.get("reasoning", "")

        except Exception:
            logger.exception("Query planning failed; defaulting to both corpora, no filter")
            # planned_source_types = (SourceType.DOCUMENT, SourceType.REPOSITORY)
            planned_filter = {
                "source_type": {
                    "$in": ["document", "repository"]
                }
            }
            # reasoning = "Fallback: planner call failed."

        return QueryPlan(
            # source_types=user_source_types or planned_source_types or (SourceType.DOCUMENT, SourceType.REPOSITORY),
            pinecone_filter=user_filter if user_filter is not None else planned_filter,
            # reasoning=reasoning,
        )