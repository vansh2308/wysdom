
# app/infrastructure/artifacts/orm_models.py
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class ArtifactStatusDB(str, PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class IngestionJobStatusDB(str, PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DocumentORM(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[ArtifactStatusDB] = mapped_column(Enum(ArtifactStatusDB, name="artifact_status"), nullable=False, default=ArtifactStatusDB.PENDING)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RepositoryORM(Base):
    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False)
    repo_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    default_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    indexed_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    languages_detected: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[ArtifactStatusDB] = mapped_column(Enum(ArtifactStatusDB, name="artifact_status"), nullable=False, default=ArtifactStatusDB.PENDING)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ChunkORM(Base):
    __tablename__ = "chunks"

    chunk_id: Mapped[str] = mapped_column(String(255), primary_key=True)  # same id used in Pinecone/BM25
    conversation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False)
    parent_type: Mapped[str] = mapped_column(String(20), nullable=False)
    parent_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IngestionJobORM(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[IngestionJobStatusDB] = mapped_column(Enum(IngestionJobStatusDB, name="ingestion_job_status"), nullable=False, default=IngestionJobStatusDB.PENDING)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)