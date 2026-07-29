
from __future__ import annotations

import re

# Heuristic only — deliberately not a blocking check. Flags chunk metadata
# for visibility; the actual defense is the system prompt instruction to
# treat retrieved content strictly as data, never as instructions.
_SUSPICIOUS_PATTERNS = [
    re.compile(r"ignore (all|previous|the above) instructions", re.IGNORECASE),
    re.compile(r"you are now (a|an) ", re.IGNORECASE),
    re.compile(r"disregard (your|all) (prior|previous) (guidance|instructions|prompt)", re.IGNORECASE),
    re.compile(r"\bsystem prompt\b", re.IGNORECASE),
]


def flag_suspected_injection(text: str) -> bool:
    return any(p.search(text) for p in _SUSPICIOUS_PATTERNS)