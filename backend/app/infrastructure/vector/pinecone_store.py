from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from pinecone import Pinecone
from langsmith import traceable

from app.core.config import get_settings
from app.knowledge.models import Chunk, ScoredChunk, SourceType


@lru_cache
def get_pinecone_client() -> Pinecone:
    settings = get_settings()
    return Pinecone(api_key=settings.PINECONE_API_KEY)


logger = logging.getLogger(__name__)

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

    async def upsert(self, chunks: list[Chunk], vectors: list[list[float]], namespace: str) -> None:
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
                    "source_id": chunk.source_id,
                    **chunk.metadata,
                },
            }
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
        async with client.IndexAsyncio(host=settings.PINECONE_INDEX_HOST) as index:
            for i in range(0, len(records), 100):  # upsert batch limit
                await index.upsert(vectors=records[i : i + 100], namespace=namespace)

    @traceable(name="dense_retrieval")
    async def query(
        self, vector: list[float], top_k: int, metadata_filter: dict[str, Any] | None, namespace: str
    ) -> list[ScoredChunk]:
        settings = get_settings()
        client = get_pinecone_client()
        async with client.IndexAsyncio(host=settings.PINECONE_INDEX_HOST) as index:
            response = await index.query(
                vector=vector,
                top_k=top_k,
                namespace=namespace,
                filter=metadata_filter or None,
                include_metadata=True,
            )

        results: list[ScoredChunk] = []
        for match in response.matches:
            metadata = dict(match.metadata or {})
            text = metadata.pop("text", "")
            source_type = SourceType(metadata.pop("source_type", SourceType.DOCUMENT.value))
            source_id = metadata.pop("source_id", "")
            results.append(
                ScoredChunk(
                    chunk=Chunk(
                        chunk_id=match.id,
                        text=text,
                        source_type=source_type,
                        source_id=source_id,
                        metadata=metadata,
                    ),
                    score=float(match.score),
                )
            )
        return results

    async def delete_namespace(self, namespace: str) -> None:
        client = get_pinecone_client()
        settings = get_settings()

        try:
            async with client.IndexAsyncio(host=settings.PINECONE_INDEX_HOST) as index:
                await index.delete(delete_all=True, namespace=namespace)
                logger.info(f"Successfully deleted Pinecone namespace: {namespace}")
        except Exception as e:
            if hasattr(e, 'status') and e.status == 404:
                logger.info(f"Namespace '{namespace}' does not exist. Skipping deletion.")
            elif "not found" in str(e).lower():
                logger.info(f"Namespace '{namespace}' not found. Skipping deletion.")
            else:
                # Re-raise if it is a genuine connection or authentication issue
                logger.error(f"Failed to delete namespace {namespace}: {e}")
                raise e
            