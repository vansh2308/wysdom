from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from app.core.config import get_settings
from app.knowledge.models import ScoredChunk


@lru_cache
def get_reranker_model():
    """Loads cross-encoder weights once per process — same pattern as the
    marker model singleton. CrossEncoder.predict is sync and CPU/GPU-bound."""
    from sentence_transformers import CrossEncoder

    return CrossEncoder(get_settings().RERANKER_MODEL_NAME)


@lru_cache
def get_reranker_executor() -> ThreadPoolExecutor:
    settings = get_settings()
    return ThreadPoolExecutor(max_workers=settings.RERANKER_WORKERS, thread_name_prefix="reranker")


class CrossEncoderReranker:
    async def rerank(self, query: str, candidates: list[ScoredChunk], top_k: int) -> list[ScoredChunk]:
        if not candidates:
            return []
        loop = asyncio.get_running_loop()
        scores = await loop.run_in_executor(get_reranker_executor(), self._score_sync, query, candidates)
        reranked = [ScoredChunk(chunk=c.chunk, score=float(s)) for c, s in zip(candidates, scores, strict=True)]
        reranked.sort(key=lambda sc: sc.score, reverse=True)
        return reranked[:top_k]

    @staticmethod
    def _score_sync(query: str, candidates: list[ScoredChunk]) -> list[float]:
        model = get_reranker_model()
        pairs = [(query, c.chunk.text) for c in candidates]
        return model.predict(pairs).tolist()