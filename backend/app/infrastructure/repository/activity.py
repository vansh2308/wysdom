
from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import ActivityRecord, ActivityType
from app.auth.orm_models import ActivityTypeDB, UserActivityORM



def _to_activity(row: UserActivityORM) -> ActivityRecord:
    return ActivityRecord(
        id=row.id, user_id=row.user_id, conversation_id=row.conversation_id,
        activity_type=ActivityType(row.activity_type.value), metadata=row.activity_metadata, created_at=row.created_at,
    )


class SqlAlchemyActivityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def log(
        self, user_id: UUID, activity_type: ActivityType, conversation_id: UUID | None, metadata: dict[str, Any]
    ) -> ActivityRecord:
        row = UserActivityORM(
            user_id=user_id, conversation_id=conversation_id,
            activity_type=ActivityTypeDB(activity_type.value), activity_metadata=metadata,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_activity(row)

    async def list_for_user(self, user_id: UUID, limit: int = 50) -> list[ActivityRecord]:
        result = await self._session.execute(
            select(UserActivityORM).where(UserActivityORM.user_id == user_id).order_by(UserActivityORM.created_at.desc()).limit(limit)
        )
        return [_to_activity(r) for r in result.scalars().all()]