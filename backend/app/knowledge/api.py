# app/api/routes/retrieval.py
from __future__ import annotations
import uuid
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import Ingestion, Retrieval, ConversationDep
from app.knowledge.schemas import DocumentIngestChunksRequest, RepositoryIngestChunksRequest, IngestionResponse, QueryPlanResponse, QueryRequest, QueryResponse, RetrievedChunkResponse
from app.knowledge.models import SourceType
from app.conversations.exceptions import ConversationNotFoundError


# router = APIRouter(prefix="/retrieval", tags=["retrieval"])
router = APIRouter(prefix="/conversations", tags=["retrieval"])


async def _get_conversation_or_404(conversations: ConversationDep, conversation_id: UUID):
    try:
        return await conversations.get_conversation(conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("{conversation_id}/ingest/pdf", response_model=IngestionResponse)
async def ingest_pdf_chunks(conversation_id: UUID, request: DocumentIngestChunksRequest, service: Ingestion, conversations: ConversationDep) -> IngestionResponse:
    conversation = await _get_conversation_or_404(conversations, conversation_id)

    source_id, count = await service.ingest(
        source_id=request.source_id or f"{uuid.uuid4().hex[:8]}",
        source_type=SourceType.DOCUMENT,
        raw_chunks=[c.model_dump() for c in request.chunks],
        shared_metadata=request.metadata,
        namespace=conversation.namespace_id
    )
    return IngestionResponse(source_id=request.source_id, source_type=SourceType.DOCUMENT, ingested_count=count)


@router.post("{conversation_id}/ingest/repository", response_model=IngestionResponse)
async def ingest_repository_chunks(conversation_id: UUID, request: RepositoryIngestChunksRequest, service: Ingestion, conversations: ConversationDep) -> IngestionResponse:
    conversation = await _get_conversation_or_404(conversations, conversation_id)

    source_id, count = await service.ingest(
        source_id=f"{uuid.uuid4().hex}",
        source_type=SourceType.REPOSITORY,
        raw_chunks=[{
            "chunk_id": chunk.id or f"{uuid.uuid4().hex}",
            "text": chunk.content,
            "metadata": {
                k: (v or 'null') for k, v in chunk.model_dump().items() if k not in {'id', 'content'}
            }
        } for chunk in request.chunks if chunk.content.strip()],
        namespace=conversation.namespace_id
    )
    return IngestionResponse(source_id=source_id, source_type=SourceType.REPOSITORY, ingested_count=count)


@router.post("{conversation_id}/query", response_model=QueryResponse)
async def query(conversation_id: UUID, request: QueryRequest, service: Retrieval, conversations: ConversationDep) -> QueryResponse:
    if not request.query.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="query must not be empty")


    conversation = await _get_conversation_or_404(conversations, conversation_id)

    result = await service.retrieve(
        query=request.query,
        user_source_types=tuple(request.source_types) if request.source_types else None,
        user_filter=request.pinecone_filter,
        final_top_k=request.top_k,
        namespace=conversation.namespace_id
    )

    return QueryResponse(
        query=result.query,
        plan=QueryPlanResponse(
            # source_types=list(result.plan.source_types),
            pinecone_filter=result.plan.pinecone_filter,
            # reasoning=result.plan.reasoning,
        ),
        structured_context=result.structured_context,
        chunks=[
            RetrievedChunkResponse(
                chunk_id=sc.chunk.chunk_id,
                text=sc.chunk.text,
                source_type=sc.chunk.source_type,
                source_id=sc.chunk.source_id,
                score=sc.score,
                metadata=sc.chunk.metadata,
            )
            for sc in result.chunks
        ],
    )