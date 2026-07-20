import uvicorn

from app.core.bootstrap import create_app
from app.core.config import get_settings

app = create_app()


# WIP: for each conversation/project create a separate vector index namespace 
# & query only with that namespace 

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
