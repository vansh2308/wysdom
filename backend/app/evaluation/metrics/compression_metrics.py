from __future__ import annotations

from typing import Any


def compression_ratio(inputs: dict, outputs: dict, reference_outputs: dict | None = None) -> dict[str, Any]:
    raw = outputs["raw_tokens"]
    compressed = outputs["compressed_tokens"]
    if raw == 0:
        return {"key": "compression_ratio", "score": None}
    return {"key": "compression_ratio", "score": 1 - (compressed / raw)}


async def retention_check(inputs: dict, outputs: dict, reference_outputs: dict) -> dict[str, Any]:
    """LLM-judge: can the probe questions still be answered using only the
    compressed context? Catches compression that saves tokens by dropping
    information that actually mattered."""
    from pydantic import BaseModel

    from app.core.config import get_settings
    from app.knowledge.embedding_client import get_openai_client

    probe_questions: list[str] = reference_outputs.get("probe_questions", [])
    if not probe_questions:
        return {"key": "retention_rate", "score": None}

    class _Answerable(BaseModel):
        answerable_flags: list[bool]

    client = get_openai_client()
    settings = get_settings()
    response = await client.responses.parse(
        model=settings.GUARDRAIL_FAITHFULNESS_MODEL,
        input=[
            {
                "role": "system",
                "content": "For each question, return true if it can be fully answered using only the given context, false otherwise. Return one boolean per question, in order.",
            },
            {"role": "user", "content": f"CONTEXT:\n{outputs['compressed_text']}\n\nQUESTIONS:\n" + "\n".join(probe_questions)},
        ],
        text_format=_Answerable,
    )
    flags = response.output_parsed.answerable_flags if response.output_parsed else []
    if not flags:
        return {"key": "retention_rate", "score": None}
    return {"key": "retention_rate", "score": sum(flags) / len(flags)}


def compression_evaluators() -> list:
    return [compression_ratio, retention_check]