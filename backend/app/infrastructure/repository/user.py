
from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.orm_models import UserORM



def _to_user(row: UserORM) -> User:
    return User(
        id=row.id, email=row.email, display_name=row.display_name,
        is_active=row.is_active, created_at=row.created_at, updated_at=row.updated_at,
    )


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UUID) -> User | None:
        row = await self._session.get(UserORM, user_id)
        return _to_user(row) if row else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(UserORM).where(UserORM.email == email))
        row = result.scalar_one_or_none()
        return _to_user(row) if row else None

    async def get_or_create_by_email(self, email: str, display_name: str | None) -> User:
        existing = await self.get_by_email(email)
        if existing is not None:
            return existing
        row = UserORM(email=email, display_name=display_name)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_user(row)