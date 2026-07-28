# app/infrastructure/agent_runs/orm_models.py
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class AgentRunStatusDB(str, PyEnum):
    PLANNING = "planning"
    RETRIEVING = "retrieving"
    CRITIQUING = "critiquing"
    SYNTHESIZING = "synthesizing"
    DONE = "done"
    FAILED = "failed"


class AgentRunORM(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False)
    message_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL"), nullable=True)
    request_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AgentRunStatusDB] = mapped_column(Enum(AgentRunStatusDB, name="agent_run_status"), nullable=False, default=AgentRunStatusDB.PLANNING)
    plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    critic_history: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    retrieval_loop_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    report: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    markdown_report: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)