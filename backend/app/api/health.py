from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", include_in_schema=False)
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
