from fastapi import APIRouter
from pydantic import BaseModel

from app.repositories.models import CodeChunk
from app.repositories.service import RepositoryChunkService

router = APIRouter(prefix="/repositories", tags=["repositories"])
service = RepositoryChunkService()


class ChunkRepositoryRequest(BaseModel):
    repo_url: str
    include_tests: bool = True


@router.post("/chunk", response_model=list[CodeChunk])
async def chunk_repository(payload: ChunkRepositoryRequest) -> list[CodeChunk]:
    return service.chunk_repository(payload.repo_url, include_tests=payload.include_tests)
