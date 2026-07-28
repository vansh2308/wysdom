

# app/domain/users/ports.py
from __future__ import annotations

from typing import Protocol, Any
from uuid import UUID

# from app.domain.users.models import User, 
from app.auth.models import User, ActivityRecord, ActivityType


class UserRepositoryPort(Protocol):
    async def get(self, user_id: UUID) -> User | None: ...
    async def get_by_email(self, email: str) -> User | None: ...
    async def get_or_create_by_email(self, email: str, display_name: str | None) -> User: ...

class ActivityRepositoryPort(Protocol):
    async def log(
        self, user_id: UUID, activity_type: ActivityType, conversation_id: UUID | None, metadata: dict[str, Any]
    ) -> ActivityRecord: ...
    async def list_for_user(self, user_id: UUID, limit: int = 50) -> list[ActivityRecord]: ...