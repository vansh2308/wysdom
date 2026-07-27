import uvicorn

from app.core.bootstrap import create_app
from app.core.config import get_settings

app = create_app()


# TODO: Migrate from openRouter to OpenAi
# TODO: Add Postgres relations
# TODO: Add conversation context 
# TODO: Add websearch, arxiv tool
# TODO: Add OAuth
# TODO: Add repo/pdf graph builder 

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
