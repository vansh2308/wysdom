

# app/domain/agent_runs/ports.py
from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

# from app.domain.agent_runs.models import AgentRun, AgentRunStatus
from app.agents.models import AgentRun, AgentStatus


class AgentRunRepositoryPort(Protocol):
    async def create(self, conversation_id: UUID, message_id: UUID | None, request_text: str) -> AgentRun: ...
    async def complete(
        self, run_id: UUID, status: AgentStatus, plan: dict[str, Any] | None,
        critic_history: list[dict[str, Any]], retrieval_loop_count: int, errors: list[str],
        report: dict[str, Any] | None, markdown_report: str | None,
    ) -> AgentRun: ...
    async def get(self, run_id: UUID) -> AgentRun | None: ...
    async def list_by_conversation(self, conversation_id: UUID) -> list[AgentRun]: ...