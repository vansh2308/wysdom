# app/api/routes/retrieval.py
from __future__ import annotations
import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import Ingestion, Retrieval
from app.knowledge.schemas import DocumentIngestChunksRequest, RepositoryIngestChunksRequest, IngestionResponse, QueryPlanResponse, QueryRequest, QueryResponse, RetrievedChunkResponse
from app.knowledge.models import SourceType

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


@router.post("/ingest/pdf", response_model=IngestionResponse)
async def ingest_pdf_chunks(request: DocumentIngestChunksRequest, service: Ingestion) -> IngestionResponse:
    source_id, count = await service.ingest(
        source_id=request.source_id or f"{uuid.uuid4().hex[:8]}",
        source_type=SourceType.DOCUMENT,
        raw_chunks=[c.model_dump() for c in request.chunks],
        shared_metadata=request.metadata,
    )
    return IngestionResponse(source_id=request.source_id, source_type=SourceType.DOCUMENT, ingested_count=count)


@router.post("/ingest/repository", response_model=IngestionResponse)
async def ingest_repository_chunks(request: RepositoryIngestChunksRequest, service: Ingestion) -> IngestionResponse:
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
    )
    return IngestionResponse(source_id=source_id, source_type=SourceType.REPOSITORY, ingested_count=count)


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest, service: Retrieval) -> QueryResponse:
    if not request.query.strip():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="query must not be empty")

    result = await service.retrieve(
        query=request.query,
        user_source_types=tuple(request.source_types) if request.source_types else None,
        user_filter=request.pinecone_filter,
        final_top_k=request.top_k,
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