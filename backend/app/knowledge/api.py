# app/api/routes/retrieval.py
from __future__ import annotations
import uuid
import logging
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, UploadFile, Depends

from app.api.dependencies import Ingestion, Retrieval, ConversationDep, PdfExtraction, RepositoryChunker, IngestionJobDep, DocumentArtifactDep, RepositoryArtifactDep
from app.knowledge.schemas import DocumentIngestChunksRequest, RepositoryIngestChunksRequest, IngestionResponse, QueryPlanResponse, QueryRequest, QueryResponse, RetrievedChunkResponse
from app.documents.pdf_extraction_service import FileTooLargeError, UnsupportedFileError
from app.infrastructure.documents.marker_extractor import MarkerExtractionError
from app.knowledge.models import SourceType
from app.conversations.exceptions import ConversationNotFoundError
from app.documents.models import ExtractionOptions
from app.knowledge.models import IngestionJobStatus, ArtifactStatus


# router = APIRouter(prefix="/retrieval", tags=["retrieval"])
router = APIRouter(prefix="/conversations", tags=["retrieval"])
logger = logging.getLogger(__name__)


async def _get_conversation_or_404(conversations: ConversationDep, conversation_id: UUID):
    try:
        return await conversations.get_conversation(conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc



@router.post("/{conversation_id}/ingest/pdf", response_model=IngestionResponse)
async def ingest_pdf_chunks(
        conversation_id: UUID,
        chunkingService: PdfExtraction,
        file: UploadFile,
        ingestionService: Ingestion,
        conversations: ConversationDep,
        documents: DocumentArtifactDep,
        jobs: IngestionJobDep,
        request: DocumentIngestChunksRequest = Depends()
    ) -> IngestionResponse:
    conversation = await _get_conversation_or_404(conversations, conversation_id)

    options = ExtractionOptions(
            output_format=request.output_format,
            use_llm=request.use_llm,
            force_ocr=request.force_ocr,
            extract_images=request.extract_images,
            page_range=request.page_range,
        )

    try:
        result = await chunkingService.extract_from_upload(file, options)
    except (UnsupportedFileError, FileTooLargeError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except MarkerExtractionError as exc:
        logger.exception("PDF extraction failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail="PDF extraction failed."
        ) from exc


    document = await documents.create(conversation_id, filename=file.filename, content_type="application/pdf")
    job = await jobs.create(conversation_id, source_type="document", source_ref=str(document.id))

    try:
        source_id, count = await ingestionService.ingest(
            source_id=file.filename or f"{uuid.uuid4().hex}",
            source_type=SourceType.DOCUMENT,
            conversation_id=conversation_id,
            raw_chunks=[c for c in result.content.get('blocks', [])],
            shared_metadata={},
            namespace=conversation.namespace_id
        )
    except Exception as exc:
        await jobs.complete(job.id, IngestionJobStatus.FAILED, error=str(exc))
        await documents.update_status(document.id, ArtifactStatus.FAILED, error=str(exc))
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Ingestion failed") from exc

    await jobs.complete(job.id, IngestionJobStatus.SUCCEEDED)
    await documents.update_status(document.id, ArtifactStatus.READY, page_count=None)
    return IngestionResponse(source_id=source_id, source_type=SourceType.DOCUMENT, ingested_count=count)




@router.post("/{conversation_id}/ingest/repository", response_model=IngestionResponse)
async def ingest_repository_chunks(
        conversation_id: UUID,
        chunkingService: RepositoryChunker,
        ingestionService: Ingestion,
        conversations: ConversationDep,
        repositories: RepositoryArtifactDep,
        jobs: IngestionJobDep,
        request: RepositoryIngestChunksRequest 
    ) -> IngestionResponse:
    conversation = await _get_conversation_or_404(conversations, conversation_id)

    try:
        chunks = chunkingService.chunk_repository(request.repo_url, include_tests=request.include_tests)
    except Exception as exc:
        logger.exception("Repository chunking failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail="Repository chunking failed."
        ) from exc

    # WIP: Handle multiple repo branches 
    repository = await repositories.create(conversation_id, repo_url=request.repo_url, default_branch=None)
    job = await jobs.create(conversation_id, source_type="repository", source_ref=str(repository.id))

    try:
        source_id, count = await ingestionService.ingest(
                source_id= request.repo_url or f"{uuid.uuid4()}",
                source_type=SourceType.REPOSITORY,
                conversation_id=conversation_id,
                raw_chunks=[{
                    "chunk_id": chunk.id or f"{uuid.uuid4().hex}",
                    "text": chunk.content,
                    "metadata": {
                        k: (v or 'null') for k, v in chunk.model_dump().items() if k not in {'id', 'content'}
                    }
                } for chunk in chunks if chunk.content.strip()],
                namespace=conversation.namespace_id
            )
    except Exception as exc:
        await jobs.complete(job.id, IngestionJobStatus.FAILED, error=str(exc))
        await repositories.update_status(repository.id, ArtifactStatus.FAILED, error=str(exc))
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail="Ingestion failed") from exc
    
    await jobs.complete(job.id, IngestionJobStatus.SUCCEEDED)
    await repositories.update_status(repository.id, ArtifactStatus.READY)
    return IngestionResponse(source_id=source_id, source_type=SourceType.REPOSITORY, ingested_count=count)


@router.post("/{conversation_id}/query", response_model=QueryResponse)
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