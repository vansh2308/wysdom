from __future__ import annotations

from typing import Any, Protocol

from app.knowledge.models import Chunk, QueryPlan, ScoredChunk, SourceType


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