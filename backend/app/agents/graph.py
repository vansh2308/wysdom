
from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy
from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError


from app.agents.models import MultiAgentState
from app.agents.nodes import critique_node, plan_node, retrieve_node, route_after_critique, synthesize_node


# Retries only kick in for transient failures — parsing/validation errors
# fall back inside the node instead (see nodes.py).
_LLM_RETRY = RetryPolicy(
    max_attempts=3,
    initial_interval=1.0,
    backoff_factor=2.0,
    retry_on=(APIConnectionError, APITimeoutError, RateLimitError, InternalServerError),
)


@lru_cache
def get_agent_graph():
    """
    Compiled once per process — the compiled graph is stateless/reusable
    across concurrent requests; all per-request data lives in the
    MultiAgentState passed into ainvoke/astream. Same singleton pattern as
    the DB engine and model registries elsewhere in the app.

    NOTE: RetryPolicy's field names (max_attempts/initial_interval/
    backoff_factor/retry_on) may shift slightly across langgraph releases —
    check langgraph.types.RetryPolicy for your installed version if this
    doesn't type-check.
    """
    builder = StateGraph(MultiAgentState)

    builder.add_node("make_plan", plan_node, retry=_LLM_RETRY)
    builder.add_node("retrieve", retrieve_node)  # failures handled internally, not node-level retried
    builder.add_node("critique", critique_node, retry=_LLM_RETRY)
    builder.add_node("synthesize", synthesize_node, retry=_LLM_RETRY)

    builder.add_edge(START, "make_plan")
    builder.add_edge("make_plan", "retrieve")
    builder.add_edge("retrieve", "critique")
    builder.add_conditional_edges("critique", route_after_critique, {"retrieve": "retrieve", "synthesize": "synthesize"})
    builder.add_edge("synthesize", END)

    return builder.compile()