from __future__ import annotations

from functools import lru_cache
from typing import Any

from pinecone import Pinecone

from app.core.config import get_settings
from app.knowledge.models import Chunk, ScoredChunk, SourceType


@lru_cache
def get_pinecone_client() -> Pinecone:
    settings = get_settings()
    return Pinecone(api_key=settings.PINECONE_API_KEY)


class PineconeVectorStore:
    """
    VectorStorePort adapter. The control-plane client is a cached singleton;
    each call opens an IndexAsyncio data-plane context (Pinecone's async
    client manages its own aiohttp session per context manager).

    NOTE: Pinecone's async surface has been renamed across SDK majors
    (PineconeAsyncio/IndexAsyncio vs AsyncPinecone). If you bump the
    `pinecone` package and this breaks, check https://sdk.pinecone.io —
    this is the only file that needs to change.
    """

    async def upsert(self, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        if not chunks:
            return
        settings = get_settings()
        client = get_pinecone_client()
        records = [
            {
                "id": chunk.chunk_id,
                "values": vector,
                "metadata": {
                    "text": chunk.text,
                    "source_type": chunk.source_type.value,
                    "parent_id": chunk.parent_id,
                    **chunk.metadata,
                },
            }
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        async with client.IndexAsyncio(host=settings.PINECONE_INDEX_HOST) as index:
            for i in range(0, len(records), 100):  # upsert batch limit
                await index.upsert(vectors=records[i : i + 100], namespace=settings.PINECONE_NAMESPACE)

    async def query(
        self, vector: list[float], top_k: int, metadata_filter: dict[str, Any] | None
    ) -> list[ScoredChunk]:
        settings = get_settings()
        client = get_pinecone_client()
        async with client.IndexAsyncio(host=settings.PINECONE_INDEX_HOST) as index:
            response = await index.query(
                vector=vector,
                top_k=top_k,
                namespace=settings.PINECONE_NAMESPACE,
                filter=metadata_filter or None,
                include_metadata=True,
            )

        results: list[ScoredChunk] = []
        for match in response.matches:
            metadata = dict(match.metadata or {})
            text = metadata.pop("text", "")
            source_type = SourceType(metadata.pop("source_type", SourceType.DOCUMENT.value))
            parent_id = metadata.pop("parent_id", "")
            results.append(
                ScoredChunk(
                    chunk=Chunk(
                        chunk_id=match.id,
                        text=text,
                        source_type=source_type,
                        parent_id=parent_id,
                        metadata=metadata,
                    ),
                    score=float(match.score),
                )
            )
        return results