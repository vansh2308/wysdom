
# app/infrastructure/agent_runs/repository.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


from app.agents.models import AgentRun, AgentStatus
from app.agents.orm_models import AgentRunORM, AgentRunStatusDB


def _to_agent_run(row: AgentRunORM) -> AgentRun:
    return AgentRun(
        id=row.id, conversation_id=row.conversation_id, message_id=row.message_id, request_text=row.request_text,
        status=AgentStatus(row.status.value), plan=row.plan, critic_history=row.critic_history,
        retrieval_loop_count=row.retrieval_loop_count, errors=row.errors, report=row.report,
        markdown_report=row.markdown_report, started_at=row.started_at, completed_at=row.completed_at,
    )


class SqlAlchemyAgentRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, conversation_id: UUID, message_id: UUID | None, request_text: str) -> AgentRun:
        row = AgentRunORM(conversation_id=conversation_id, message_id=message_id, request_text=request_text)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_agent_run(row)

    async def complete(
        self, run_id: UUID, status: AgentStatus, plan: dict[str, Any] | None,
        critic_history: list[dict[str, Any]], retrieval_loop_count: int, errors: list[str],
        report: dict[str, Any] | None, markdown_report: str | None,
    ) -> AgentRun:
        row = await self._session.get(AgentRunORM, run_id)
        if row is None:
            raise LookupError(f"agent run {run_id} not found")
        row.status = AgentRunStatusDB(status.value)
        row.plan = plan
        row.critic_history = critic_history
        row.retrieval_loop_count = retrieval_loop_count
        row.errors = errors
        row.report = report
        row.markdown_report = markdown_report
        row.completed_at = datetime.now(timezone.utc)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_agent_run(row)

    async def get(self, run_id: UUID) -> AgentRun | None:
        row = await self._session.get(AgentRunORM, run_id)
        return _to_agent_run(row) if row else None

    async def list_by_conversation(self, conversation_id: UUID) -> list[AgentRun]:
        result = await self._session.execute(
            select(AgentRunORM).where(AgentRunORM.conversation_id == conversation_id).order_by(AgentRunORM.started_at.asc())
        )
        return [_to_agent_run(r) for r in result.scalars().all()]