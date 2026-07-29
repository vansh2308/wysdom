
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class GuardrailSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    BLOCK = "block"


class GuardrailFinding(BaseModel):
    check: str
    severity: GuardrailSeverity
    message: str
    evidence: str | None = None


class GuardrailVerdict(BaseModel):
    passed: bool
    findings: list[GuardrailFinding]
    sanitized_content: str | None = None  