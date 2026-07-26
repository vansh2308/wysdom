# app/infrastructure/conversations/repository.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.conversations.models import Conversation, ConversationStatus, Message, MessageRole
from app.conversations.orm_models import ConversationORM, ConversationStatusDB, MessageORM, MessageRoleDB

def _to_conversation(row: ConversationORM) -> Conversation:
    return Conversation(
        id=row.id, owner_id=row.owner_id, namespace_id=row.namespace_id, name=row.name,
        status=ConversationStatus(row.status.value), message_count=row.message_count,
        created_at=row.created_at, updated_at=row.updated_at,
    )


def _to_message(row: MessageORM) -> Message:
    return Message(
        id=row.id, conversation_id=row.conversation_id, role=MessageRole(row.role.value),
        content=row.content, created_at=row.created_at,
    )


class SqlAlchemyConversationRepository:
    """Implements both ConversationRepositoryPort and MessageRepositoryPort.
    Takes a request-scoped AsyncSession — never caches it, never holds it
    beyond the request. Methods flush (so generated ids/defaults are visible
    immediately) but never commit — the request-scoped session dependency
    owns the transaction boundary."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, owner_id: str, namespace_id: str) -> Conversation:
        row = ConversationORM(owner_id=owner_id, namespace_id=namespace_id, status=ConversationStatusDB.DRAFT)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_conversation(row)

    async def get(self, conversation_id: UUID) -> Conversation | None:
        row = await self._session.get(ConversationORM, conversation_id)
        return _to_conversation(row) if row else None

    async def list_by_owner(self, owner_id: str) -> list[Conversation]:
        result = await self._session.execute(
            select(ConversationORM).where(ConversationORM.owner_id == owner_id).order_by(ConversationORM.updated_at.desc())
        )
        return [_to_conversation(r) for r in result.scalars().all()]

    async def set_name_and_activate(self, conversation_id: UUID, name: str) -> Conversation:
        row = await self._session.get(ConversationORM, conversation_id)
        if row is None:
            raise LookupError(f"conversation {conversation_id} not found")
        row.name = name
        row.status = ConversationStatusDB.ACTIVE
        await self._session.flush()
        await self._session.refresh(row)
        return _to_conversation(row)

    async def increment_message_count(self, conversation_id: UUID) -> int:
        row = await self._session.get(ConversationORM, conversation_id)
        if row is None:
            raise LookupError(f"conversation {conversation_id} not found")
        row.message_count += 1
        await self._session.flush()
        return row.message_count

    async def delete(self, conversation_id: UUID) -> None:
        row = await self._session.get(ConversationORM, conversation_id)
        if row is not None:
            await self._session.delete(row)
            await self._session.flush()

    async def list_stale_drafts(self, older_than: timedelta) -> list[Conversation]:
        cutoff = datetime.now(timezone.utc) - older_than
        result = await self._session.execute(
            select(ConversationORM).where(
                ConversationORM.status == ConversationStatusDB.DRAFT, ConversationORM.created_at < cutoff
            )
        )
        return [_to_conversation(r) for r in result.scalars().all()]

    async def add_message(self, conversation_id: UUID, role: MessageRole, content: str) -> Message:
        row = MessageORM(conversation_id=conversation_id, role=MessageRoleDB(role.value), content=content)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row)
        return _to_message(row)

    async def list_messages(self, conversation_id: UUID) -> list[Message]:
        result = await self._session.execute(
            select(MessageORM).where(MessageORM.conversation_id == conversation_id).order_by(MessageORM.created_at.asc())
        )
        return [_to_message(r) for r in result.scalars().all()]