# app/application/services/retrieval_service.py
from __future__ import annotations

import asyncio
from typing import List

from app.core.config import get_settings
from app.knowledge.fusion import reciprocal_rank_fusion
from app.knowledge.models import QueryPlan, RetrievalResult, ScoredChunk, SourceType
from app.knowledge.ports import ContextCompressorPort, EmbeddingPort, KeywordIndexPort, QueryPlannerPort, RerankerPort, VectorStorePort


class RetrievalService:
    """plan -> (dense || keyword) -> RRF fuse -> cross-encoder rerank ->
    LLM context compression -> structured result."""

    def __init__(
        self,
        planner: QueryPlannerPort,
        embedder: EmbeddingPort,
        vector_store: VectorStorePort,
        keyword_index: KeywordIndexPort,
        reranker: RerankerPort,
        compressor: ContextCompressorPort,
    ) -> None:
        self._planner = planner
        self._embedder = embedder
        self._vector_store = vector_store
        self._keyword_index = keyword_index
        self._reranker = reranker
        self._compressor = compressor

    async def retrieve(
        self,
        query: str,
        namespace: str,
        user_source_types: tuple[SourceType, ...] | None,
        user_filter: dict | None,
        final_top_k: int | None = None,
    ) -> RetrievalResult:
        settings = get_settings()

        plan = await self._planner.plan(query, user_source_types, user_filter)
        # pinecone_filter = self._merge_source_type_filter(plan)
        pinecone_filter = plan.pinecone_filter
        source_types: List[str] = pinecone_filter.get("source_types", {}).get("$in", ["document", "repository"])
        query_vector = await self._embedder.embed_query(query)

        dense_results, keyword_results = await asyncio.gather(
            self._vector_store.query(query_vector, settings.RETRIEVAL_DENSE_TOP_K, pinecone_filter, namespace=namespace),
            self._keyword_index.search(query, settings.RETRIEVAL_KEYWORD_TOP_K, source_types, plan.pinecone_filter),
        )

        by_id = {sc.chunk.chunk_id: sc for sc in [*dense_results, *keyword_results]}
        
        fused_scores = reciprocal_rank_fusion(
            [[sc.chunk.chunk_id for sc in dense_results], [sc.chunk.chunk_id for sc in keyword_results]],
            k=settings.RRF_K,
        )
        fused_ranked = sorted(fused_scores.items(), key=lambda pair: pair[1], reverse=True)
        candidates = [
            ScoredChunk(chunk=by_id[cid].chunk, score=score)
            for cid, score in fused_ranked[: settings.RETRIEVAL_RERANK_TOP_N]
        ]

        reranked = await self._reranker.rerank(query, candidates, final_top_k or settings.RETRIEVAL_FINAL_TOP_K)

        structured_context = await self._compressor.compress(query, reranked)

        return RetrievalResult(query=query, plan=plan, chunks=tuple(reranked), structured_context=structured_context)

    @staticmethod
    def _merge_source_type_filter(plan: QueryPlan) -> dict:
        base = dict(plan.pinecone_filter or {})
        if plan.source_types:
            base["source_type"] = {"$in": [st.value for st in plan.source_types]}
        return base