from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger = logging.getLogger("wysdom.bootstrap")
        logger.info("Application startup complete for %s", resolved_settings.app_name)
        try:
            yield
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
    return app
