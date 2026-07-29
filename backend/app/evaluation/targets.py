from __future__ import annotations

import uuid
from datetime import datetime, timezone

import tiktoken

from app.agents.orchestration_service import AgentOrchestrationService
from app.knowledge.retrieval_service import RetrievalService
from app.core.config import get_settings

from app.conversations.models import Conversation, ConversationStatus
from app.infrastructure.vector.bm25_index import Bm25KeywordIndex
from app.knowledge.context_compressor import LlmContextCompressor
from app.knowledge.embedding_client import OpenAiEmbeddingClient
from app.infrastructure.vector.pinecone_store import PineconeVectorStore
from app.agents.query_planner import LlmQueryPlanner
from app.knowledge.reranker import CrossEncoderReranker


_ENCODING = tiktoken.get_encoding("cl100k_base")


def _build_eval_retrieval_service() -> RetrievalService:
    return RetrievalService(
        planner=LlmQueryPlanner(), embedder=OpenAiEmbeddingClient(), vector_store=PineconeVectorStore(),
        keyword_index=Bm25KeywordIndex(), reranker=CrossEncoderReranker(), compressor=LlmContextCompressor(),
    )


async def dense_retrieval_target(inputs: dict) -> dict:
    """Dense-only, per the explicit eval scope — bypasses BM25/RRF/rerank
    entirely, calling PineconeVectorStore.query() directly."""
    settings = get_settings()
    embedder = OpenAiEmbeddingClient()
    vector_store = PineconeVectorStore()
    vector = await embedder.embed_query(inputs["query"])
    results = await vector_store.query(vector, top_k=settings.EVAL_RETRIEVAL_TOP_K, metadata_filter=None, namespace=inputs["namespace"])
    return {"retrieved_chunk_ids": [sc.chunk.chunk_id for sc in results]}


async def compression_target(inputs: dict) -> dict:
    """Reuses RetrievalService.retrieve() end-to-end rather than duplicating
    the compression call — result.chunks is the pre-compression (reranked)
    set, result.structured_context is post-compression. Both are already
    computed by a single real call."""
    retrieval_service = _build_eval_retrieval_service()
    result = await retrieval_service.retrieve(query=inputs["query"], namespace=inputs["namespace"], user_source_types=None, user_filter=None)
    raw_text = "\n\n".join(sc.chunk.text for sc in result.chunks)
    return {
        "raw_tokens": len(_ENCODING.encode(raw_text)),
        "compressed_tokens": len(_ENCODING.encode(result.structured_context)),
        "compressed_text": result.structured_context,
    }


async def agent_target(inputs: dict) -> dict:
    """Ad hoc Conversation stub — no Postgres row, no OpenAI conversation
    thread (openai_conversation_id=None), isolated LangGraph checkpointer
    thread_id so eval runs never touch real conversation state."""
    orchestration = AgentOrchestrationService()
    conversation = Conversation(
        id=uuid.uuid4(), owner_id=uuid.uuid4(), namespace_id=inputs["namespace"],
        name="eval", status=ConversationStatus.ACTIVE, message_count=0,
        created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
    )
    # state = await orchestration.run(conversation, inputs["query"], thread_id=f"eval_{uuid.uuid4().hex}")
    state = await orchestration.run(inputs["query"], inputs["namespace"], thread_id=f"eval_{uuid.uuid4().hex}")
    return state.model_dump(mode="json")


# answer_quality reuses the same full agent run — same target function
answer_quality_target = agent_target