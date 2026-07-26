# app/application/services/conversation_service.py
from __future__ import annotations

import logging
import uuid
from datetime import timedelta
from uuid import UUID

from app.conversations.exceptions import ConversationNotFoundError, NamespaceDeletionError
from app.conversations.models import Conversation, Message, MessageRole, ConversationStatus
from app.conversations.ports import ConversationNamerPort, ConversationRepositoryPort, MessageRepositoryPort
from app.knowledge.ports import VectorStorePort

logger = logging.getLogger(__name__)


class ConversationService:
    def __init__(
        self,
        conversations: ConversationRepositoryPort,
        messages: MessageRepositoryPort,
        namer: ConversationNamerPort,
        vector_store: VectorStorePort,
    ) -> None:
        self._conversations = conversations
        self._messages = messages
        self._namer = namer
        self._vector_store = vector_store

    async def create_conversation(self, owner_id: str) -> Conversation:
        namespace_id = f"conv_{uuid.uuid4().hex}"
        return await self._conversations.create(owner_id=owner_id, namespace_id=namespace_id)

    async def get_conversation(self, conversation_id: UUID) -> Conversation:
        conversation = await self._conversations.get(conversation_id)
        if conversation is None:
            raise ConversationNotFoundError(str(conversation_id))
        return conversation

    async def list_conversations(self, owner_id: str) -> list[Conversation]:
        return await self._conversations.list_by_owner(owner_id)

    async def add_message(self, conversation_id: UUID, role: MessageRole, content: str) -> tuple[Message, Conversation]:
        conversation = await self.get_conversation(conversation_id)

        message = await self._messages.add_message(conversation_id, role, content)
        new_count = await self._conversations.increment_message_count(conversation_id)

        if conversation.status is ConversationStatus.DRAFT and new_count == 1 and role is MessageRole.USER:
            name = await self._namer.predict_name(content)
            conversation = await self._conversations.set_name_and_activate(conversation_id, name)

        return message, conversation

    async def list_messages(self, conversation_id: UUID) -> list[Message]:
        await self.get_conversation(conversation_id)  # 404s if missing
        return await self._messages.list_messages(conversation_id)

    async def delete_conversation(self, conversation_id: UUID) -> None:
        conversation = await self.get_conversation(conversation_id)
        try:
            await self._vector_store.delete_namespace(conversation.namespace_id)
        except Exception as exc:
            logger.exception("Failed to delete Pinecone namespace %s", conversation.namespace_id)
            raise NamespaceDeletionError(
                f"Could not delete vectors for conversation {conversation_id}; aborting to avoid orphaned data."
            ) from exc
        await self._conversations.delete(conversation_id)

    async def cleanup_stale_drafts(self, older_than: timedelta) -> int:
        """Best-effort sweep for DRAFT conversations that never got a message.
        Skips (rather than force-deletes) any conversation whose namespace
        cleanup fails, so it's retried on the next sweep instead of silently
        losing track of orphaned vectors."""
        stale = await self._conversations.list_stale_drafts(older_than)
        deleted = 0
        for conv in stale:
            try:
                await self._vector_store.delete_namespace(conv.namespace_id)
            except Exception:
                logger.exception("Failed to clean up namespace for stale draft %s", conv.id)
                continue
            await self._conversations.delete(conv.id)
            deleted += 1
        return deleted