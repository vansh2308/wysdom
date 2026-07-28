from typing import AsyncIterator, Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_session_factory
from app.documents.ports import PdfExtractorPort
from app.infrastructure.documents.marker_extractor import MarkerPdfExtractor
from app.documents.pdf_extraction_service import PdfExtractionService


from app.knowledge.ingestion_service import IngestionService
from app.knowledge.retrieval_service import RetrievalService
from app.knowledge.ports import ContextCompressorPort, EmbeddingPort, KeywordIndexPort, QueryPlannerPort, RerankerPort, VectorStorePort, DocumentArtifactRepositoryPort, RepositoryArtifactRepositoryPort, IngestionJobRepositoryPort, ChunkRepositoryPort
from infrastructure.repository.artifacts import SqlAlchemyDocumentArtifactRepository, SqlAlchemyIngestionJobRepository, SqlAlchemyRepositoryArtifactRepository
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
from app.repositories.service import RepositoryChunkService


from app.agents.ports import AgentRunRepositoryPort
from app.auth.ports import UserRepositoryPort, ActivityRepositoryPort
from app.infrastructure.repository.activity import SqlAlchemyActivityRepository
from app.infrastructure.repository.agent_runs import SqlAlchemyAgentRunRepository
from app.infrastructure.repository.artifacts import SqlAlchemyChunkRepository
from app.infrastructure.repository.user import SqlAlchemyUserRepository
from app.auth.activity_service import ActivityService



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

PdfExtraction = Annotated[PdfExtractionService, Depends(get_pdf_extraction_service)]

def get_repo_chunk_service() -> RepositoryChunkService:
    return RepositoryChunkService()

RepositoryChunker = Annotated[RepositoryChunkService, Depends(get_repo_chunk_service)]


def get_embedder() -> EmbeddingPort: return OpenAiEmbeddingClient()
def get_vector_store() -> VectorStorePort: return PineconeVectorStore()
def get_keyword_index() -> KeywordIndexPort: return Bm25KeywordIndex()
def get_reranker() -> RerankerPort: return CrossEncoderReranker()
def get_query_planner() -> QueryPlannerPort: return LlmQueryPlanner()
def get_context_compressor() -> ContextCompressorPort: return LlmContextCompressor()


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

Retrieval = Annotated[RetrievalService, Depends(get_retrieval_service)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_agent_orchestration_service() -> AgentOrchestrationService:
    return AgentOrchestrationService()

AgentOrchestration = Annotated[AgentOrchestrationService, Depends(get_agent_orchestration_service)]


def get_conversation_namer() -> ConversationNamerPort:
    return LlmConversationNamer()


# def get_conversation_service(session: DbSession) -> ConversationService:
#     repo = SqlAlchemyConversationRepository(session)
#     return ConversationService(
#         conversations=repo, messages=repo, namer=get_conversation_namer(), vector_store=PineconeVectorStore()
#     )









def get_user_repository(session: DbSession) -> UserRepositoryPort:
    return SqlAlchemyUserRepository(session)

UserDep = Annotated[UserRepositoryPort, Depends(get_user_repository)]


def get_activity_service(session: DbSession) -> ActivityService:
    return ActivityService(conversations=SqlAlchemyConversationRepository(session), activity=SqlAlchemyActivityRepository(session))

def get_activity_repository(session: DbSession) -> ActivityRepositoryPort:
    return SqlAlchemyActivityRepository(session)

ActivityDep = Annotated[ActivityRepositoryPort, Depends(get_activity_repository)]


def get_conversation_service(
    session: DbSession,
    users: Annotated[UserRepositoryPort, Depends(get_user_repository)],
    activity: Annotated[ActivityService, Depends(get_activity_service)],
) -> ConversationService:
    repo = SqlAlchemyConversationRepository(session)
    return ConversationService(
        conversations=repo, messages=repo, namer=get_conversation_namer(), vector_store=PineconeVectorStore(),
        users=users, activity=activity,
    )

ConversationDep = Annotated[ConversationService, Depends(get_conversation_service)]


def get_ingestion_service(
    session: DbSession,
    embedder: Annotated[EmbeddingPort, Depends(get_embedder)],
    vector_store: Annotated[VectorStorePort, Depends(get_vector_store)],
    keyword_index: Annotated[KeywordIndexPort, Depends(get_keyword_index)],
) -> IngestionService:
    return IngestionService(embedder, vector_store, keyword_index, chunk_repository=SqlAlchemyChunkRepository(session))

Ingestion = Annotated[IngestionService, Depends(get_ingestion_service)]


def get_agent_run_repository(session: DbSession) -> AgentRunRepositoryPort:
    return SqlAlchemyAgentRunRepository(session)


def get_document_artifact_repository(session: DbSession) -> DocumentArtifactRepositoryPort:
    return SqlAlchemyDocumentArtifactRepository(session)


def get_repository_artifact_repository(session: DbSession) -> RepositoryArtifactRepositoryPort:
    return SqlAlchemyRepositoryArtifactRepository(session)


def get_ingestion_job_repository(session: DbSession) -> IngestionJobRepositoryPort:
    return SqlAlchemyIngestionJobRepository(session)

def get_chunk_repository(session: DbSession) -> ChunkRepositoryPort:
    return SqlAlchemyChunkRepository(session)


AgentRunRepositoryDep = Annotated[AgentRunRepositoryPort, Depends(get_agent_run_repository)]
ChunkRepositoryDep = Annotated[ChunkRepositoryPort, Depends(get_chunk_repository)]
DocumentArtifactDep = Annotated[DocumentArtifactRepositoryPort, Depends(get_document_artifact_repository)]
RepositoryArtifactDep = Annotated[RepositoryArtifactRepositoryPort, Depends(get_repository_artifact_repository)]
IngestionJobDep = Annotated[IngestionJobRepositoryPort, Depends(get_ingestion_job_repository)]