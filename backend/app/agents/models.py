
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.knowledge.models import SourceType


class AgentStatus(str, Enum):
    PLANNING = "planning"
    RETRIEVING = "retrieving"
    CRITIQUING = "critiquing"
    SYNTHESIZING = "synthesizing"
    DONE = "done"
    FAILED = "failed"


# --- LLM-facing models (kept free of dict/Any fields — OpenAI structured
# outputs' strict JSON schema mode doesn't support open-ended dicts) ---

class PlanStep(BaseModel):
    step_id: str
    description: str
    retrieval_query: str
    depends_on: list[str] = Field(default_factory=list)
    source_types: list[SourceType] = Field(default_factory=list)  # empty = let the retrieval engine's own planner decide


class ExecutionPlan(BaseModel):
    steps: list[PlanStep]
    reasoning: str


class CriticVerdict(BaseModel):
    is_sufficient: bool
    missing_aspects: list[str] = Field(default_factory=list)
    refinement_steps: list[PlanStep] = Field(default_factory=list)
    reasoning: str


class ExplainabilityReport(BaseModel):
    summary: str
    reasoning_summary: str  # mandatory "how we got here" per your Explainability contract
    supporting_evidence: list[str]
    confidence: Literal["low", "medium", "high"]
    references: list[str]
    related_reading: list[str]
    alternative_interpretations: list[str] = Field(default_factory=list)


# --- internal/derived models (not LLM output, can hold dicts freely) ---

class RetrievedChunkPayload(BaseModel):
    chunk_id: str
    text: str
    source_type: SourceType
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievedStepResult(BaseModel):
    step_id: str
    query: str
    structured_context: str
    chunks: list[RetrievedChunkPayload]
    error: str | None = None


class MultiAgentState(BaseModel):
    request_id: str
    user_request: str
    plan: ExecutionPlan | None = None
    step_results: dict[str, RetrievedStepResult] = Field(default_factory=dict)
    critic_history: list[CriticVerdict] = Field(default_factory=list)
    retrieval_loop_count: int = 0
    max_retrieval_loops: int = 2
    status: AgentStatus = AgentStatus.PLANNING
    errors: list[str] = Field(default_factory=list)
    report: ExplainabilityReport | None = None
    markdown_report: str | None = None