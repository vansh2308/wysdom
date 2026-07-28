from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from datetime import datetime
from uuid import UUID


class SourceType(str, Enum):
    DOCUMENT = "document"
    REPOSITORY = "repository"


@dataclass(frozen=True, slots=True)
class Chunk:
    chunk_id: str
    text: str
    source_type: SourceType
    source_id: str  # document_id or repository_id
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class QueryPlan:
    # source_types: tuple[SourceType, ...]
    pinecone_filter: dict[str, Any]
    # reasoning: str


@dataclass(frozen=True, slots=True)
class ScoredChunk:
    chunk: Chunk
    score: float


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    query: str
    plan: QueryPlan
    chunks: tuple[ScoredChunk, ...]
    structured_context: str



class ArtifactStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class IngestionJobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class DocumentArtifact:
    id: UUID
    conversation_id: UUID
    filename: str
    content_type: str
    status: ArtifactStatus
    page_count: int | None
    extraction_metadata: dict[str, Any]
    error: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class RepositoryArtifact:
    id: UUID
    conversation_id: UUID
    repo_url: str
    default_branch: str | None
    indexed_commit_sha: str | None
    languages_detected: list[str]
    status: ArtifactStatus
    error: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ChunkRecord:
    chunk_id: str
    conversation_id: UUID
    parent_type: str  # "document" | "repository"
    parent_id: str
    text: str
    metadata: dict[str, Any]
    token_count: int | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class IngestionJob:
    id: UUID
    conversation_id: UUID
    source_type: str  # "document" | "repository"
    source_ref: str
    status: IngestionJobStatus
    error: str | None
    started_at: datetime
    completed_at: datetime | None