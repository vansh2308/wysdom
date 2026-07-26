

# app/domain/conversations/models.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class ConversationStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class Conversation:
    id: UUID
    owner_id: str
    namespace_id: str
    name: str | None
    status: ConversationStatus
    message_count: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class Message:
    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    created_at: datetime