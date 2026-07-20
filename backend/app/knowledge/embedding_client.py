from __future__ import annotations

from app.core.config import get_settings

from app.infrastructure.llm.llm_client import get_openai_client



class OpenAiEmbeddingClient:
    """EmbeddingPort adapter. The client itself is the cached singleton
    (connection pooling); this wrapper is stateless and cheap per request."""

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        settings = get_settings()
        client = get_openai_client()
        response = await client.embeddings.create(
            model=settings.EMBEDDING_MODEL,
            input=texts,
            # dimension=settings.EMBEDDING_DIMENSION
            encoding_format="float"
        )
        return [item.embedding for item in response.data]

    async def embed_query(self, query: str) -> list[float]:
        vectors = await self.embed_texts([query])
        return vectors[0]