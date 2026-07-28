from __future__ import annotations

from typing import Any, Protocol
from uuid import UUID

from app.knowledge.models import Chunk, QueryPlan, ScoredChunk, SourceType, ArtifactStatus, DocumentArtifact, RepositoryArtifact, ChunkRecord, IngestionJob, IngestionJobStatus


class EmbeddingPort(Protocol):
    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...
    async def embed_query(self, query: str) -> list[float]: ...


class VectorStorePort(Protocol):
    async def upsert(self, chunks: list[Chunk], vectors: list[list[float]], namespace: str) -> None: ...
    async def query(
        self, vector: list[float], top_k: int, metadata_filter: dict[str, Any] | None, namespace: str
    ) -> list[ScoredChunk]: ...
    async def delete_namespace(self, namespace: str) -> None: ...


class KeywordIndexPort(Protocol):
    async def add_documents(self, chunks: list[Chunk]) -> None: ...
    async def search(
        self,
        query: str,
        top_k: int,
        source_types: tuple[SourceType, ...] | None,
        metadata_filter: dict[str, Any] | None,
    ) -> list[ScoredChunk]: ...


class RerankerPort(Protocol):
    async def rerank(
        self, query: str, candidates: list[ScoredChunk], top_k: int
    ) -> list[ScoredChunk]: ...


class QueryPlannerPort(Protocol):
    async def plan(
        self,
        query: str,
        user_source_types: tuple[SourceType, ...] | None,
        user_filter: dict[str, Any] | None,
    ) -> QueryPlan: ...


class ContextCompressorPort(Protocol):
    async def compress(self, query: str, chunks: list[ScoredChunk]) -> str: ...







class DocumentArtifactRepositoryPort(Protocol):
    async def create(self, conversation_id: UUID, filename: str, content_type: str) -> DocumentArtifact: ...
    async def update_status(
        self, document_id: UUID, status: ArtifactStatus, page_count: int | None = None,
        extraction_metadata: dict[str, Any] | None = None, error: str | None = None,
    ) -> DocumentArtifact: ...
    async def get(self, document_id: UUID) -> DocumentArtifact | None: ...
    async def list_by_conversation(self, conversation_id: UUID) -> list[DocumentArtifact]: ...


class RepositoryArtifactRepositoryPort(Protocol):
    async def create(self, conversation_id: UUID, repo_url: str, default_branch: str | None) -> RepositoryArtifact: ...
    async def update_status(
        self, repository_id: UUID, status: ArtifactStatus, indexed_commit_sha: str | None = None,
        languages_detected: list[str] | None = None, error: str | None = None,
    ) -> RepositoryArtifact: ...
    async def get(self, repository_id: UUID) -> RepositoryArtifact | None: ...
    async def list_by_conversation(self, conversation_id: UUID) -> list[RepositoryArtifact]: ...


class ChunkRepositoryPort(Protocol):
    async def bulk_insert(self, conversation_id: UUID, parent_type: str, parent_id: str, chunks: list[Chunk]) -> int: ...
    async def list_by_parent(self, parent_id: str) -> list[ChunkRecord]: ...
    async def list_by_conversation(self, conversation_id: UUID) -> list[ChunkRecord]: ...

class IngestionJobRepositoryPort(Protocol):
    async def create(self, conversation_id: UUID, source_type: str, source_ref: str) -> IngestionJob: ...
    async def complete(self, job_id: UUID, status: IngestionJobStatus, error: str | None = None) -> IngestionJob: ...