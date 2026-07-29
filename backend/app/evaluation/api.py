from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, status

from app.evaluation.schemas import RunEvalRequest, RunEvalResponse
from app.core.config import get_settings
from app.evaluation.runner import run_eval_suite

router = APIRouter(prefix="/eval", tags=["eval"])


@router.post("/run", response_model=RunEvalResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_eval(request: RunEvalRequest, background_tasks: BackgroundTasks) -> RunEvalResponse:
    """
    Fires the eval suite as a background task and returns immediately —
    suites involve many LLM calls per case and aren't a fit for a blocking
    HTTP request/response cycle. Results, progress, and per-case detail are
    all in the LangSmith UI under this experiment_prefix, not polled here.
    """
    settings = get_settings()
    experiment_prefix = f"{request.suite.value}-{uuid.uuid4().hex[:8]}"
    background_tasks.add_task(run_eval_suite, request.suite, request.dataset_name, request.max_concurrency, experiment_prefix)
    return RunEvalResponse(experiment_prefix=experiment_prefix, status="started", langsmith_project=settings.LANGSMITH_PROJECT)