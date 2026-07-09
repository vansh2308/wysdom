from fastapi import APIRouter
from sqlalchemy import text

from app.api.dependencies import DbSession

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", include_in_schema=False)
async def health_check() -> dict[str, str]:
    return {"status": "ok"}



@router.get("/db", include_in_schema=False)
async def health_db_check(session: DbSession) -> dict[str, str]:
    await session.execute(text("SELECT 1"))
    return {"status": "ok", "database": "reachable"}
