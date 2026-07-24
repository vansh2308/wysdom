from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.api import router as auth_router
from app.api.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.infrastructure.database.session import get_engine, dispose_engine
from app.repositories.api import router as repositories_router
from app.documents.api import router as documents_router
from app.knowledge.api import router as knowledge_router
from app.agents.api import router as agents_router
from app.infrastructure.documents.model_registry import get_artifact_dict
from app.infrastructure.vector.bm25_index import Bm25KeywordIndex


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger = logging.getLogger("wysdom.bootstrap")
        logger.info("Application startup complete for %s", resolved_settings.app_name)
        
        try:
            get_engine()
            if resolved_settings.PDF_EXTRACTION_EAGER_LOAD_MODELS:
                get_artifact_dict()
            Bm25KeywordIndex.load_from_disk()
            yield
            await dispose_engine() 
        finally:
            logger.info("Application shutdown complete for %s", resolved_settings.app_name)



    app = FastAPI(
        title=resolved_settings.app_name,
        version="0.1.0",
        debug=resolved_settings.debug,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.logger = logging.getLogger("wysdom.bootstrap")

    origins = [
        "http://localhost",
    ]  
    app.add_middleware(
        CORSMiddleware,
        allow_origins = origins,
        allow_credentials = True,
        allow_methods = ["*"],
        allow_headers = ["*"]
    )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(repositories_router)
    app.include_router(documents_router)
    app.include_router(knowledge_router)
    app.include_router(agents_router)
    return app
