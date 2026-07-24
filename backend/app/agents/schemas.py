
from __future__ import annotations

from pydantic import BaseModel

from app.agents.models import AgentStatus, CriticVerdict, ExecutionPlan, ExplainabilityReport, RetrievedStepResult

class AgentRunRequest(BaseModel):
    request: str


class AgentRunResponse(BaseModel):
    request_id: str
    status: AgentStatus
    plan: ExecutionPlan | None
    step_results: dict[str, RetrievedStepResult]
    critic_history: list[CriticVerdict]
    retrieval_loop_count: int
    errors: list[str]
    report: ExplainabilityReport | None
    markdown_report: str | None