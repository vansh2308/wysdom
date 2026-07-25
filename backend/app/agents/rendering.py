from __future__ import annotations

from app.agents.models import ExplainabilityReport, MultiAgentState


def _bullets(items: list[str]) -> list[str]:
    return [f"- {item}" for item in items] if items else ["- (none)"]


def render_markdown_report(state: MultiAgentState, report: ExplainabilityReport) -> str:
    sections = [
        f"# {state.user_request}",
        "",
        "## Detailed Response",
        report.detailed_response,
        "",
        "## Reasoning Summary",
        report.reasoning_summary,
        "",
        "## Supporting Evidence",
        *_bullets(report.supporting_evidence),
        "",
        f"## Confidence: {report.confidence.upper()}",
        "",
        "## References",
        *_bullets(report.references),
        "",
        "## Related Reading",
        *_bullets(report.related_reading),
    ]
    if report.alternative_interpretations:
        sections += ["", "## Alternative Interpretations", *_bullets(report.alternative_interpretations)]
    return "\n".join(sections)