# query_planner.py
from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import get_settings

from app.knowledge.models import QueryPlan, SourceType
from app.infrastructure.llm.llm_client import get_openai_client, get_anthropic_client


logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a retrieval query planner for a hybrid search engine over two corpora: \"document\" chunks (from PDFs/papers) and \"repository\" chunks (parsed source code). Given a user's query, decide: \n - which source_types are relevant (\"document\", \"repository\", or both) \n - a Pinecone metadata filter matching the query hints. The filter must strictly use this conditional format: \n   {\n     \"$or\": [\n       {\n         \"$and\": [\n           {\"sourceType\": {\"$eq\": \"document\"}},\n           {\"page\": {\"$in\": [page_range]}}\n         ]\n       },\n       {\n         \"$and\": [\n           {\"sourceType\": {\"$eq\": \"repository\"}},\n           {\"language\": {\"$in\": [languages_set]}}\n         ]\n       }\n     ]\n   }\n   Omit either branch of the \"$or\" array if that specific sourceType is not relevant to the query. Use an empty object {} if no specific page ranges or languages are implied. \n Focus on the source (where you will get the relevant chunk) in the vector RAG. For eg. if the query is \"Give C++ code based on the algorithm given on page 2-3 of the pdf\", the relevant vector embeddings are the pdf (document) with page filter in the range 2-3 \n Respond with ONLY a JSON object (raw text not code block), no other text, matching exactly: \n {\"source_types\": [\"document\"|\"repository\", ...], \"filter\": {...}}.
"""


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
                extra_body={"reasoning": {"enabled": True}}
            )

            raw_text = response.choices[0].message.content
            parsed = json.loads(raw_text)
            planned_source_types = tuple(SourceType(s) for s in parsed.get("source_types", []))
            planned_filter = parsed.get("filter", {}) or {}
            reasoning = parsed.get("reasoning", "")

        except Exception:
            logger.exception("Query planning failed; defaulting to both corpora, no filter")
            planned_source_types = (SourceType.DOCUMENT, SourceType.REPOSITORY)
            planned_filter = {}
            reasoning = "Fallback: planner call failed."

        return QueryPlan(
            source_types=user_source_types or planned_source_types or (SourceType.DOCUMENT, SourceType.REPOSITORY),
            pinecone_filter=user_filter if user_filter is not None else planned_filter,
            reasoning=reasoning,
        )