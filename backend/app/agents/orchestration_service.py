from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from langgraph.errors import GraphRecursionError

from app.agents.graph import get_agent_graph
from app.agents.models import AgentStatus, MultiAgentState
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class AgentOrchestrationService:
    """Thin wrapper around the compiled graph: builds initial state,
    invokes/streams it, and guarantees the caller always gets a
    MultiAgentState back rather than a raw graph exception."""

    async def run(self, user_request: str, namespace: str, thread_id: str) -> MultiAgentState:
        graph = get_agent_graph()
        settings = get_settings()
        initial_state = MultiAgentState(
            request_id=uuid.uuid4().hex,
            user_request=user_request,
            max_retrieval_loops=settings.AGENT_MAX_RETRIEVAL_LOOPS,
            namespace=namespace,
            max_guardrail_retries=settings.MAX_GUARDRAIL_RETRIES
        )

        try:
            result = await graph.ainvoke(
                initial_state.model_dump(), 
                config={"configurable": {"thread_id": thread_id}, "recursion_limit": settings.AGENT_RECURSION_LIMIT}
                # config={"recursion_limit": settings.AGENT_RECURSION_LIMIT}
            )
        except GraphRecursionError:
            logger.exception("Agent graph exceeded recursion limit for request %s", initial_state.request_id)
            return initial_state.model_copy(
                update={"status": AgentStatus.FAILED, "errors": [*initial_state.errors, "Graph exceeded recursion limit."]}
            )
        except Exception as exc:
            logger.exception("Agent graph run failed for request %s", initial_state.request_id)
            return initial_state.model_copy(update={"status": AgentStatus.FAILED, "errors": [*initial_state.errors, f"Unhandled error: {exc}"]})

        return MultiAgentState.model_validate(result)

    async def stream(self, user_request: str, namespace: str, thread_id: str) -> AsyncIterator[dict[str, Any]]:
        """Yields {"node": name, "update": {...}} per completed node — maps
        to the platform's Streaming requirement (current step/agent/progress)."""
        graph = get_agent_graph()
        settings = get_settings()
        initial_state = MultiAgentState(
            request_id=uuid.uuid4().hex, user_request=user_request, max_retrieval_loops=settings.AGENT_MAX_RETRIEVAL_LOOPS
        )

        try:
            async for event in graph.astream(
                initial_state.model_dump(), 
                config={"configurable": {"thread_id": thread_id}, "recursion_limit": settings.AGENT_RECURSION_LIMIT}, 
                stream_mode="updates"
            ):
                for node_name, update in event.items():
                    yield {"node": node_name, "update": update}
        except GraphRecursionError:
            logger.exception("Agent graph exceeded recursion limit (stream) for request %s", initial_state.request_id)
            yield {"node": "error", "update": {"error": "recursion_limit_exceeded"}}
        except Exception as exc:
            logger.exception("Agent graph stream failed for request %s", initial_state.request_id)
            yield {"node": "error", "update": {"error": str(exc)}}