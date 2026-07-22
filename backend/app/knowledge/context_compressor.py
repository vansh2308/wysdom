from __future__ import annotations

import logging

from app.core.config import get_settings
from app.knowledge.models import ScoredChunk
from app.infrastructure.llm.llm_client import get_openai_client


logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You compress retrieved search results into a single, \
deduplicated context block for another AI system to reason over. Preserve \
all technically relevant facts, identifiers, and figures. Cite each fact's \
origin using its bracketed id, e.g. [chunk_3f2a]. Output only the compressed \
context, no commentary."""


class LlmContextCompressor:
    async def compress(self, query: str, chunks: list[ScoredChunk]) -> str:
        if not chunks:
            return ""
        settings = get_settings()
        # client = get_anthropic_client()
        client = get_openai_client()

        formatted = "\n\n".join(
            f"[chunk_{sc.chunk.chunk_id}] (score={sc.score:.3f})\n{sc.chunk.text}" for sc in chunks
        )
        try:
            # response = await client.messages.create(
            #     model=settings.CONTEXT_COMPRESSOR_MODEL,
            #     max_tokens=2048,
            #     system=_SYSTEM_PROMPT,
            #     messages=[{
            #         "role": "user", 
            #         "content": f"Query: {query}\n\nRetrieved chunks:\n\n{formatted}"
            #     }],
            # )
            # return "".join(b.text for b in response.content if b.type == "text")

            response = await client.chat.completions.create(
                model = settings.CONTEXT_COMPRESSOR_MODEL,
                messages = [
                    { "role": "system", "content": _SYSTEM_PROMPT },
                    { "role": "user", "content": f"Query: {query}\n\nRetrieved chunks:\n\n{formatted}" },
                ],
                extra_body={"reasoning": {"enabled": False}}
            )
            return response.choices[0].message.content

        except Exception:
            logger.exception("Context compression failed; falling back to raw concatenation")
            return formatted