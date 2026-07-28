

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.auth.models import ActivityType
from app.auth.ports import ActivityRepositoryPort
from app.conversations.ports import ConversationRepositoryPort

logger = logging.getLogger(__name__)


class ActivityService:
    """Resolves owner_id from conversation_id once, so callers never have
    to look up the conversation themselves just to log an event."""

    def __init__(self, conversations: ConversationRepositoryPort, activity: ActivityRepositoryPort) -> None:
        self._conversations = conversations
        self._activity = activity

    async def record(self, conversation_id: UUID, activity_type: ActivityType, metadata: dict[str, Any]) -> None:
        conversation = await self._conversations.get(conversation_id)
        if conversation is None:
            logger.warning("Skipping activity log for missing conversation %s", conversation_id)
            return
        await self._activity.log(conversation.owner_id, activity_type, conversation_id, metadata)