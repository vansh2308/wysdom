from typing import AsyncIterator, Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_session_factory
from app.documents.ports import PdfExtractorPort
from app.infrastructure.documents.marker_extractor import MarkerPdfExtractor
from app.documents.pdf_extraction_service import PdfExtractionService


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

# Convenience alias for route signatures
DbSession = Annotated[AsyncSession, Depends(get_db_session)]