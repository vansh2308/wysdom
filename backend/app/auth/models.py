
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from enum import Enum
from typing import Any
from dataclasses import dataclass

class LoginRequest(BaseModel):
    user_id: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeResponse(BaseModel):
    user_id: str


@dataclass(frozen=True, slots=True)
class User(BaseModel):
    id: UUID
    email: str | None
    display_name: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime



class ActivityType(str, Enum):
    CONVERSATION_CREATED = "conversation_created"
    CONVERSATION_DELETED = "conversation_deleted"
    MESSAGE_SENT = "message_sent"
    DOCUMENT_INGESTED = "document_ingested"
    REPOSITORY_INGESTED = "repository_ingested"
    AGENT_RUN_COMPLETED = "agent_run_completed"
    AGENT_RUN_FAILED = "agent_run_failed"


@dataclass(frozen=True, slots=True)
class ActivityRecord:
    id: UUID
    user_id: UUID
    conversation_id: UUID | None
    activity_type: ActivityType
    metadata: dict[str, Any]
    created_at: datetime