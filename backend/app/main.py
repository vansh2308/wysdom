import uvicorn

from app.core.bootstrap import create_app
from app.core.config import get_settings

app = create_app()


# TODO: Migrate from openRouter to OpenAi
# TODO: Add conversation context 
# TODO: Chunk repo .md as well
# TODO: Add websearch, arxiv tool, graphBuilder

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
