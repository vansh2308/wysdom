# app/api/schemas/retrieval.py
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field

from app.knowledge.models import SourceType
from app.repositories.schemas import CodeChunk
from app.documents.models import ExtractionOutputFormat

class ChunkInput(BaseModel):
    chunk_id: str | None = None
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


# class DocumentIngestChunksRequest(BaseModel):
#     source_id: str = Field(..., description="document_id or repository_id these chunks belong to")
#     chunks: list[ChunkInput]
#     metadata: dict[str, Any] = Field(default_factory=dict, description="Shared metadata merged into every chunk")


class DocumentIngestChunksRequest(BaseModel):
    output_format: ExtractionOutputFormat = Field(
        default=ExtractionOutputFormat.CHUNKS,
        description="The desired format for the extracted output."
    )
    use_llm: bool = Field(
        default=False, 
        description="Whether to use an LLM for processing."
    )
    force_ocr: bool = Field(
        default=False, 
        description="Force optical character recognition on the document."
    )
    extract_images: bool = Field(
        default=False, 
        description="Enable extraction of images from the file."
    )
    page_range: Optional[str] = Field(
        default=None, 
        description="Specific page range to process, e.g., '1-5'."
    )


# class RepositoryIngestChunksRequest(BaseModel): 
#     chunks: List[CodeChunk]

class RepositoryIngestChunksRequest(BaseModel): 
    repo_url: str
    include_tests: bool = True

class IngestionResponse(BaseModel):
    source_id: str
    source_type: SourceType
    ingested_count: int


class QueryRequest(BaseModel):
    query: str
    top_k: int | None = None
    source_types: list[SourceType] | None = None
    pinecone_filter: dict[str, Any] | None = Field(
        default=None, description="Explicit Pinecone metadata filter; overrides the planner's."
    )


class RetrievedChunkResponse(BaseModel):
    chunk_id: str
    text: str
    source_type: SourceType
    source_id: str
    score: float
    metadata: dict[str, Any]


class QueryPlanResponse(BaseModel):
    # source_types: list[SourceType]
    pinecone_filter: dict[str, Any]
    # reasoning: str


class QueryResponse(BaseModel):
    query: str
    plan: QueryPlanResponse
    structured_context: str
    chunks: list[RetrievedChunkResponse]