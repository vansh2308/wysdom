from __future__ import annotations

from pydantic import BaseModel, Field

from app.evaluation.runner import EvalSuite


class RunEvalRequest(BaseModel):
    suite: EvalSuite
    dataset_name: str
    max_concurrency: int = Field(default=4, ge=1, le=20)


class RunEvalResponse(BaseModel):
    experiment_prefix: str
    status: str
    langsmith_project: str