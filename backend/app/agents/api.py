# app/api/routes/agents.py
from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.dependencies import AgentOrchestration
from app.agents.schemas import AgentRunRequest, AgentRunResponse

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/run", response_model=AgentRunResponse)
async def run_agents(request: AgentRunRequest, service: AgentOrchestration) -> AgentRunResponse:
    state = await service.run(request.request)
    return AgentRunResponse(**state.model_dump())


@router.post("/run/stream")
async def run_agents_stream(request: AgentRunRequest, service: AgentOrchestration) -> StreamingResponse:
    async def event_source():
        async for event in service.stream(request.request):
            yield json.dumps(event, default=str) + "\n"

    return StreamingResponse(event_source(), media_type="application/x-ndjson")