from __future__ import annotations

import re

from app.guardrails.models import GuardrailFinding, GuardrailSeverity

# High-confidence patterns only — deliberately narrow to avoid false-positive
# redaction of legitimate technical content (hashes, tokens in code examples).
_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("private_key_header", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("openai_style_key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("generic_bearer_token", re.compile(r"Bearer [A-Za-z0-9\-_.]{20,}")),
]


def scan_for_secrets(text: str) -> tuple[str, list[GuardrailFinding]]:
    """Deterministic, synchronous, no LLM call. Redacts in place — callers
    should treat these findings as already-resolved, not retry-worthy."""
    findings: list[GuardrailFinding] = []
    sanitized = text
    for name, pattern in _PATTERNS:
        if pattern.search(sanitized):
            findings.append(
                GuardrailFinding(
                    check=f"secret_scan:{name}",
                    severity=GuardrailSeverity.BLOCK,
                    message=f"Detected a possible {name.replace('_', ' ')} in the generated response; redacted.",
                )
            )
            sanitized = pattern.sub("[REDACTED]", sanitized)
    return sanitized, findings