# app/application/services/ingestion_service.py
from __future__ import annotations

from uuid import UUID, uuid4
from typing import Tuple

from app.knowledge.models import Chunk, SourceType
from app.knowledge.ports import EmbeddingPort, KeywordIndexPort, VectorStorePort, ChunkRepositoryPort

class IngestionService:
    """Shared path for document and repository chunks: embed -> upsert dense
    vectors -> add to keyword index. Both writes happen every time so BM25
    and Pinecone never drift apart."""

    def __init__(
            self, 
            embedder: EmbeddingPort, 
            vector_store: VectorStorePort, 
            keyword_index: KeywordIndexPort,
            chunk_repository: ChunkRepositoryPort,
        ) -> None:
        self._embedder = embedder
        self._vector_store = vector_store
        self._keyword_index = keyword_index
        self._chunk_repository = chunk_repository    

    async def ingest(
        self, 
        conversation_id: UUID,
        source_id: str, 
        namespace: str, 
        source_type: SourceType, 
        raw_chunks: list[dict], 
        shared_metadata: dict = {}
    ) -> Tuple[str, int]:
        chunks = [
            Chunk(
                chunk_id=raw.get("chunk_id") or f"{source_id}_{uuid4().hex[:8]}",
                text=raw["text"],
                source_type=source_type,
                source_id=source_id,
                metadata={**shared_metadata, **raw.get("metadata", {})},
            )
            for raw in raw_chunks
            if raw.get("text", "").strip()
        ]
        if not chunks:
            return 0

        vectors = await self._embedder.embed_texts([c.text for c in chunks])
        await self._vector_store.upsert(chunks, vectors, namespace=namespace)
        await self._keyword_index.add_documents(chunks)
        await self._chunk_repository.bulk_insert(conversation_id, source_type, source_id, chunks)
        return (source_id, len(chunks))