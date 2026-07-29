
from __future__ import annotations

import re

from app.guardrails.models import GuardrailFinding, GuardrailSeverity

_CITATION_PATTERN = re.compile(r"\[chunk_([A-Za-z0-9_]+)\]")


def check_citations(text: str, valid_chunk_ids: set[str]) -> list[GuardrailFinding]:
    """Deterministic — every cited chunk_id must exist among what was
    actually retrieved this turn. Catches invented sources outright."""
    cited = {f"chunk_{m}" if not m.startswith("chunk_") else m for m in _CITATION_PATTERN.findall(text)}
    invalid = cited - valid_chunk_ids
    if not invalid:
        return []
    return [
        GuardrailFinding(
            check="citation_grounding",
            severity=GuardrailSeverity.BLOCK,
            message=f"Response cites {len(invalid)} chunk id(s) that were not actually retrieved this turn.",
            evidence=", ".join(sorted(invalid)[:10]),
        )
    ]