# app/api/schemas/users.py
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class GetOrCreateUserRequest(BaseModel):
    email: EmailStr
    display_name: str | None = None


class UserResponse(BaseModel):
    id: UUID
    email: str | None
    display_name: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime