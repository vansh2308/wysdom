from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict

from app.conversations.models import ConversationStatus, MessageRole


class CreateConversationRequest(BaseModel):
    # No auth system yet, so owner_id is client-supplied. Once auth exists,
    # this should come from a verified session dependency, not the body.
    owner_id: str = Field(..., min_length=1, max_length=255)


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    owner_id: str
    namespace_id: str
    name: str | None
    status: ConversationStatus
    message_count: int
    created_at: datetime
    updated_at: datetime


class CreateMessageRequest(BaseModel):
    role: MessageRole
    content: str = Field(..., min_length=1)


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    conversation_id: UUID
    role: MessageRole
    content: str
    created_at: datetime


class CleanupDraftsResponse(BaseModel):
    deleted_count: int