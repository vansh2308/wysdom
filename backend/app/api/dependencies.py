from typing import AsyncIterator, Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_session_factory
from app.documents.ports import PdfExtractorPort
from app.infrastructure.documents.marker_extractor import MarkerPdfExtractor
from app.documents.pdf_extraction_service import PdfExtractionService


from app.knowledge.ingestion_service import IngestionService
from app.knowledge.retrieval_service import RetrievalService
from app.knowledge.ports import ContextCompressorPort, EmbeddingPort, KeywordIndexPort, QueryPlannerPort, RerankerPort, VectorStorePort
from app.knowledge.context_compressor import LlmContextCompressor
from app.infrastructure.vector.bm25_index import Bm25KeywordIndex
from app.infrastructure.vector.pinecone_store import PineconeVectorStore
from app.knowledge.embedding_client import OpenAiEmbeddingClient
from app.agents.query_planner import LlmQueryPlanner
from app.knowledge.reranker import CrossEncoderReranker
from app.agents.orchestration_service import AgentOrchestrationService
from app.conversations.ports import ConversationNamerPort
from app.conversations.namer import LlmConversationNamer
from app.conversations.conversation_service import ConversationService
from app.infrastructure.repository.conversations import SqlAlchemyConversationRepository



async def get_db_session() -> AsyncIterator[AsyncSession]:
    """
    Request-scoped session pulled from the shared singleton pool.
    Rolls back on unhandled exceptions; commit is the caller's responsibility
    (repository / unit-of-work), not this dependency's.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_pdf_extractor() -> PdfExtractorPort:
    # Stateless adapter, cheap to build per request — the real singleton
    # state (model weights, executor) lives behind lru_cache in infra.
    return MarkerPdfExtractor()


def get_pdf_extraction_service(
    extractor: Annotated[PdfExtractorPort, Depends(get_pdf_extractor)],
) -> PdfExtractionService:
    return PdfExtractionService(extractor)


def get_embedder() -> EmbeddingPort: return OpenAiEmbeddingClient()
def get_vector_store() -> VectorStorePort: return PineconeVectorStore()
def get_keyword_index() -> KeywordIndexPort: return Bm25KeywordIndex()
def get_reranker() -> RerankerPort: return CrossEncoderReranker()
def get_query_planner() -> QueryPlannerPort: return LlmQueryPlanner()
def get_context_compressor() -> ContextCompressorPort: return LlmContextCompressor()


def get_ingestion_service(
    embedder: Annotated[EmbeddingPort, Depends(get_embedder)],
    vector_store: Annotated[VectorStorePort, Depends(get_vector_store)],
    keyword_index: Annotated[KeywordIndexPort, Depends(get_keyword_index)],
) -> IngestionService:
    return IngestionService(embedder, vector_store, keyword_index)


def get_retrieval_service(
    planner: Annotated[QueryPlannerPort, Depends(get_query_planner)],
    embedder: Annotated[EmbeddingPort, Depends(get_embedder)],
    vector_store: Annotated[VectorStorePort, Depends(get_vector_store)],
    keyword_index: Annotated[KeywordIndexPort, Depends(get_keyword_index)],
    reranker: Annotated[RerankerPort, Depends(get_reranker)],
    compressor: Annotated[ContextCompressorPort, Depends(get_context_compressor)],
) -> RetrievalService:
    return RetrievalService(planner, embedder, vector_store, keyword_index, reranker, compressor)


# Convenience alias for route signatures
Ingestion = Annotated[IngestionService, Depends(get_ingestion_service)]
Retrieval = Annotated[RetrievalService, Depends(get_retrieval_service)]
PdfExtraction = Annotated[PdfExtractionService, Depends(get_pdf_extraction_service)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_agent_orchestration_service() -> AgentOrchestrationService:
    return AgentOrchestrationService()

AgentOrchestration = Annotated[AgentOrchestrationService, Depends(get_agent_orchestration_service)]


def get_conversation_namer() -> ConversationNamerPort:
    return LlmConversationNamer()


def get_conversation_service(session: DbSession) -> ConversationService:
    repo = SqlAlchemyConversationRepository(session)
    return ConversationService(
        conversations=repo, messages=repo, namer=get_conversation_namer(), vector_store=PineconeVectorStore()
    )


ConversationDep = Annotated[ConversationService, Depends(get_conversation_service)]