from __future__ import annotations

import logging
from datetime import timedelta
from uuid import UUID, uuid4
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Query, status, Response

from app.api.dependencies import ConversationDep, AgentOrchestration, AgentRunRepositoryDep
from app.conversations.schemas import CleanupDraftsResponse, ConversationResponse, CreateConversationRequest, CreateMessageRequest, MessageResponse
from app.conversations.exceptions import ConversationNotFoundError, NamespaceDeletionError
from app.agents.schemas import AgentRunResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/conversations", tags=["conversations"])

# NOTE: this must be registered before "/{conversation_id}" routes below —
# otherwise "maintenance" would be matched (and fail UUID parsing) as a
# conversation_id path param instead of reaching this route.
@router.post("/maintenance/cleanup-drafts", response_model=CleanupDraftsResponse)
async def cleanup_stale_drafts(
    service: ConversationDep,
    older_than_hours: int = Query(default=24, ge=1, description="Delete DRAFT conversations with 0 messages older than this"),
) -> CleanupDraftsResponse:
    deleted = await service.cleanup_stale_drafts(timedelta(hours=older_than_hours))
    return CleanupDraftsResponse(deleted_count=deleted)


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: CreateConversationRequest, service: ConversationDep
) -> ConversationResponse:
    conversation = await service.create_conversation(owner_id=request.owner_id)
    
    logger.info(conversation)
    # return ConversationResponse(**conversation.__dict__)
    # return ConversationResponse(**vars(conversation))
    return ConversationResponse.model_validate(conversation)


@router.get("", response_model=list[ConversationResponse])
async def list_conversations(
    service: ConversationDep,
    owner_id: str = Query(..., min_length=1, description="Owner to list conversations for"),
) -> list[ConversationResponse]:
    conversations = await service.list_conversations(owner_id=owner_id)
    return [ConversationResponse.model_validate(c) for c in conversations]


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(conversation_id: UUID, service: ConversationDep) -> ConversationResponse:
    try:
        conversation = await service.get_conversation(conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    # return ConversationResponse(**conversation.__dict__)
    return ConversationResponse.model_validate(conversation)


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_message(
    conversation_id: UUID, 
    request: CreateMessageRequest,
    conversationService: ConversationDep,
    agentRunRepoService: AgentRunRepositoryDep,
    agentService: AgentOrchestration
) -> MessageResponse:
    try:
        message, _conversation = await conversationService.add_message(
            conversation_id=conversation_id, role=request.role, content=request.content
        )

        run = await agentRunRepoService.create(conversation_id, message.id, message.content)
        state = await agentService.run(user_request=request.content, namespace=_conversation.namespace_id, thread_id=uuid4().hex)

        await agentRunRepoService.complete(
            run.id, status=state.status,  
            plan=state.plan.model_dump() if state.plan else None,
            critic_history=[c.model_dump() for c in state.critic_history],
            retrieval_loop_count=state.retrieval_loop_count, errors=state.errors,
            report=state.report.model_dump() if state.report else None, markdown_report=state.markdown_report,
        )

        agent_response = AgentRunResponse(**state.model_dump())

    except ConversationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    
    return MessageResponse(
        **asdict(message),
        agent_response=agent_response
    )


@router.get("/{conversation_id}/messages", response_model=list[MessageResponse])
async def list_messages(conversation_id: UUID, service: ConversationDep) -> list[MessageResponse]:
    try:
        messages = await service.list_messages(conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    # return [MessageResponse(**m.__dict__) for m in messages]
    return [MessageResponse.model_validate(m) for m in messages]



@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: UUID, service: ConversationDep) -> Response:
    try:
        await service.delete_conversation(conversation_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ConversationNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except NamespaceDeletionError as exc:
        logger.error("Namespace deletion failed for conversation %s: %s", conversation_id, exc)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="Could not delete the conversation's vector data; the conversation was not deleted. Please retry.",
        ) from exc