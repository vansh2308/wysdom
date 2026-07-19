# app/application/services/ingestion_service.py
from __future__ import annotations

import uuid


from app.knowledge.models import Chunk, SourceType
from app.knowledge.ports import EmbeddingPort, KeywordIndexPort, VectorStorePort


class IngestionService:
    """Shared path for document and repository chunks: embed -> upsert dense
    vectors -> add to keyword index. Both writes happen every time so BM25
    and Pinecone never drift apart."""

    def __init__(self, embedder: EmbeddingPort, vector_store: VectorStorePort, keyword_index: KeywordIndexPort) -> None:
        self._embedder = embedder
        self._vector_store = vector_store
        self._keyword_index = keyword_index

    async def ingest(
        self, parent_id: str, source_type: SourceType, raw_chunks: list[dict], shared_metadata: dict
    ) -> int:
        chunks = [
            Chunk(
                chunk_id=raw.get("chunk_id") or f"{parent_id}_{uuid.uuid4().hex[:8]}",
                text=raw["text"],
                source_type=source_type,
                parent_id=parent_id,
                metadata={**shared_metadata, **raw.get("metadata", {})},
            )
            for raw in raw_chunks
            if raw.get("text", "").strip()
        ]
        if not chunks:
            return 0

        vectors = await self._embedder.embed_texts([c.text for c in chunks])
        await self._vector_store.upsert(chunks, vectors)
        await self._keyword_index.add_documents(chunks)
        return len(chunks)