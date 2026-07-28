from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth.service import AuthTokenService, get_current_user_id
from app.auth.models import LoginRequest, TokenResponse, MeResponse
from app.auth.schemas import UserResponse, GetOrCreateUserRequest
from app.api.dependencies import UserDep

router = APIRouter(prefix="/auth", tags=["auth"])



@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> TokenResponse:
    if not payload.user_id.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_id is required")

    token = AuthTokenService.create_token(payload.user_id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=MeResponse)
async def me(user_id: str = Depends(get_current_user_id)) -> MeResponse:
    return MeResponse(user_id=user_id)



@router.post("", response_model=UserResponse)
async def get_or_create_user(request: GetOrCreateUserRequest, users: UserDep) -> UserResponse:
    user = await users.get_or_create_by_email(request.email, request.display_name)
    return UserResponse(**user.__dict__)