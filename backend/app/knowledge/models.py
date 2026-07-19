from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SourceType(str, Enum):
    DOCUMENT = "document"
    REPOSITORY = "repository"


@dataclass(frozen=True, slots=True)
class Chunk:
    chunk_id: str
    text: str
    source_type: SourceType
    parent_id: str  # document_id or repository_id
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class QueryPlan:
    source_types: tuple[SourceType, ...]
    pinecone_filter: dict[str, Any]
    reasoning: str


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