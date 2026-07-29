from __future__ import annotations

from typing import Any


def faithfulness_from_run(inputs: dict, outputs: dict, reference_outputs: dict | None = None) -> dict[str, Any]:
    """Reuses the guardrail node's own faithfulness finding rather than
    re-running an LLM judge call — the real run already did this check."""
    findings = outputs.get("guardrail_findings", [])
    faithfulness_findings = [f for f in findings if f.get("check") == "faithfulness"]
    if not faithfulness_findings:
        return {"key": "faithfulness", "score": 1.0}
    return {"key": "faithfulness", "score": 0.0}


async def completeness(inputs: dict, outputs: dict, reference_outputs: dict) -> dict[str, Any]:
    from pydantic import BaseModel

    from app.core.config import get_settings
    from app.knowledge.embedding_client import get_openai_client

    rubric_points: list[str] = reference_outputs.get("rubric", [])
    report = outputs.get("report") or {}
    detailed_response = report.get("detailed_response", "")
    if not rubric_points or not detailed_response:
        return {"key": "completeness", "score": None}

    class _Coverage(BaseModel):
        covered_flags: list[bool]

    client = get_openai_client()
    settings = get_settings()
    response = await client.responses.parse(
        model=settings.GUARDRAIL_FAITHFULNESS_MODEL,
        input=[
            {"role": "system", "content": "For each rubric point, return true if the response adequately addresses it, false otherwise. One boolean per point, in order."},
            {"role": "user", "content": f"RESPONSE:\n{detailed_response}\n\nRUBRIC POINTS:\n" + "\n".join(rubric_points)},
        ],
        text_format=_Coverage,
    )
    flags = response.output_parsed.covered_flags if response.output_parsed else []
    if not flags:
        return {"key": "completeness", "score": None}
    return {"key": "completeness", "score": sum(flags) / len(flags)}


def confidence_calibration(inputs: dict, outputs: dict, reference_outputs: dict) -> dict[str, Any]:
    """Requires a human-graded is_correct label in the dataset. Rewards
    high confidence when correct and low confidence when incorrect;
    penalizes confident-but-wrong (the worst failure mode) more than
    hedged-but-wrong."""
    report = outputs.get("report") or {}
    confidence = report.get("confidence")
    is_correct = reference_outputs.get("is_correct")
    if confidence is None or is_correct is None:
        return {"key": "confidence_calibration", "score": None}

    if is_correct:
        score = {"high": 1.0, "medium": 0.7, "low": 0.4}.get(confidence, 0.5)
    else:
        score = {"low": 0.7, "medium": 0.3, "high": 0.0}.get(confidence, 0.5)
    return {"key": "confidence_calibration", "score": score}


def answer_quality_evaluators() -> list:
    return [faithfulness_from_run, completeness, confidence_calibration]