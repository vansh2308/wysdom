
from __future__ import annotations

import asyncio
import logging
from typing import Literal

from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

from app.agents.models import AgentStatus, CriticVerdict, ExecutionPlan, ExplainabilityReport, MultiAgentState, PlanStep, RetrievedChunkPayload, RetrievedStepResult
from app.agents.rendering import render_markdown_report
from app.agents.query_planner import LlmQueryPlanner

from app.core.config import get_settings
from app.infrastructure.vector.bm25_index import Bm25KeywordIndex
from app.infrastructure.vector.pinecone_store import PineconeVectorStore

from app.knowledge.retrieval_service import RetrievalService
from app.knowledge.context_compressor import LlmContextCompressor
from app.knowledge.embedding_client import OpenAiEmbeddingClient, get_openai_client
from app.knowledge.reranker import CrossEncoderReranker

logger = logging.getLogger(__name__)

# Only these are retried by RetryPolicy — everything else (bad output,
# refusals, validation errors) falls back immediately instead of retrying.
_TRANSIENT_OPENAI_ERRORS = (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)


def _build_retrieval_service() -> RetrievalService:
    """Mirrors get_retrieval_service() in api/dependencies.py, but standalone
    since LangGraph node functions have a fixed (state) -> dict signature and
    can't take FastAPI-style constructor injection."""
    return RetrievalService(
        planner=LlmQueryPlanner(),
        embedder=OpenAiEmbeddingClient(),
        vector_store=PineconeVectorStore(),
        keyword_index=Bm25KeywordIndex(),
        reranker=CrossEncoderReranker(),
        compressor=LlmContextCompressor(),
    )


# ---------------------------------------------------------------- Planner

_PLANNER_SYSTEM_PROMPT = """You are the Planner Agent in a multi-agent engineering \
research system. Break the user's technical request into an execution DAG of \
retrieval steps. Each step is a focused sub-query against a hybrid document/code \
retrieval engine. Use depends_on only when a step genuinely needs another \
step's findings first — independent steps should have no dependencies so they \
run in parallel. Prefer 2-5 steps. Assign short, unique, lowercase step_ids \
(e.g. "s1", "s2").
\n\nCRITICAL: Return ONLY raw JSON matching the required schema. Never wrap output in markdown fences, backticks, or '```json'."""


async def plan_node(state: MultiAgentState) -> dict:
    """Planner Agent: decomposes the request into a sequential/parallel DAG."""
    client = get_openai_client()
    settings = get_settings()
    try:
        response = await client.responses.parse(
            model=settings.AGENT_PLANNER_MODEL,
            input=[
                {"role": "system", "content": _PLANNER_SYSTEM_PROMPT},
                {"role": "user", "content": state.user_request},
            ],
            text_format=ExecutionPlan,
        )
        plan = response.output_parsed
        if not plan or not plan.steps:
            raise ValueError("Planner returned an empty plan")
    except _TRANSIENT_OPENAI_ERRORS:
        raise  # let RetryPolicy re-invoke this node
    except Exception as exc:
        logger.exception("Planner agent failed; falling back to a single-step plan")
        plan = ExecutionPlan(
            steps=[PlanStep(step_id="s1", retrieval_query=state.user_request, description=state.user_request)],
            reasoning=f"Fallback plan — planner error: {exc}",
        )

    return {"plan": plan, "status": AgentStatus.RETRIEVING}


# --------------------------------------------------------------- Retriever

def _ready_steps(plan: ExecutionPlan, done_ids: set[str]) -> list[PlanStep]:
    return [s for s in plan.steps if s.step_id not in done_ids and set(s.depends_on) <= done_ids]


async def _run_step(service: RetrievalService, step: PlanStep) -> RetrievedStepResult:
    result = await service.retrieve(
        query=step.retrieval_query,
        user_source_types=tuple(step.source_types) if step.source_types else None,
        user_filter=None,
    )
    return RetrievedStepResult(
        step_id=step.step_id,
        query=step.retrieval_query,
        structured_context=result.structured_context,
        chunks=[
            RetrievedChunkPayload(
                chunk_id=sc.chunk.chunk_id,
                text=sc.chunk.text,
                source_type=sc.chunk.source_type,
                score=sc.score,
                metadata=sc.chunk.metadata,
            )
            for sc in result.chunks
        ],
    )


async def retrieve_node(state: MultiAgentState) -> dict:
    """Retriever Agent: runs the DAG's ready steps in topological waves —
    each wave runs concurrently, waves run sequentially to honor depends_on.
    Per-step failures are isolated and never abort the wave or the request."""
    assert state.plan is not None
    retrieval_service = _build_retrieval_service()

    step_results = dict(state.step_results)
    errors = list(state.errors)
    done_ids = set(step_results.keys())

    while True:
        ready = _ready_steps(state.plan, done_ids)
        if not ready:
            break

        outcomes = await asyncio.gather(
            *(_run_step(retrieval_service, step) for step in ready), return_exceptions=True
        )

        for step, outcome in zip(ready, outcomes, strict=True):
            if isinstance(outcome, Exception):
                logger.exception("Retrieval step %s failed", step.step_id)
                errors.append(f"step {step.step_id} failed: {outcome}")
                step_results[step.step_id] = RetrievedStepResult(
                    step_id=step.step_id, query=step.retrieval_query, structured_context="", chunks=[], error=str(outcome)
                )
            else:
                step_results[step.step_id] = outcome
            done_ids.add(step.step_id)

    unresolved = [s.step_id for s in state.plan.steps if s.step_id not in done_ids]
    if unresolved:
        errors.append(f"unresolved steps (unmet/cyclic dependencies): {unresolved}")

    return {"step_results": step_results, "errors": errors, "status": AgentStatus.CRITIQUING}


# ------------------------------------------------------------------ Critic

_CRITIC_SYSTEM_PROMPT = """You are the Critic Agent. Assess whether the \
retrieved context is sufficient to fully answer the user's request — check \
specifically for missing code specifics (exact function/class names, \
signatures) and missing algorithmic detail (an algorithm's steps, complexity, \
or a paper's exact method) if the request implies either. If insufficient, \
propose 1-3 targeted refinement_steps (new PlanStep objects with unique \
step_ids not already used) with narrower retrieval_query values aimed at \
exactly what's missing. 
\n\nCRITICAL: Return ONLY raw JSON matching the required schema. Never wrap output in markdown fences, backticks, or '```json'. """


async def critique_node(state: MultiAgentState) -> dict:
    assert state.plan is not None
    client = get_openai_client()
    settings = get_settings()

    context_blob = "\n\n".join(
        f"[step {sid}] query={res.query}\n{res.structured_context or '(no context retrieved)'}"
        for sid, res in state.step_results.items()
    )
    user_content = f"User request: {state.user_request}\n\nRetrieved context so far:\n\n{context_blob}"

    try:
        response = await client.responses.parse(
            model=settings.AGENT_CRITIC_MODEL,
            input=[
                {"role": "system", "content": _CRITIC_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            text_format=CriticVerdict,
        )
        verdict = response.output_parsed
        if verdict is None:
            raise ValueError("Critic returned no parsed output")
    except _TRANSIENT_OPENAI_ERRORS:
        raise
    except Exception as exc:
        logger.exception("Critic agent failed; assuming context is sufficient to avoid stalling")
        verdict = CriticVerdict(is_sufficient=True, reasoning=f"Fallback: critic error, proceeding as-is ({exc})")

    updates: dict = {"critic_history": [*state.critic_history, verdict]}

    if not verdict.is_sufficient and state.retrieval_loop_count < state.max_retrieval_loops:
        existing_ids = {s.step_id for s in state.plan.steps}
        deduped_new_steps: list[PlanStep] = []
        for s in verdict.refinement_steps:
            sid = s.step_id
            suffix = 1
            while sid in existing_ids:
                sid = f"{s.step_id}_{suffix}"
                suffix += 1
            existing_ids.add(sid)
            deduped_new_steps.append(s.model_copy(update={"step_id": sid}))

        if deduped_new_steps:
            updates["plan"] = state.plan.model_copy(update={"steps": [*state.plan.steps, *deduped_new_steps]})
        updates["retrieval_loop_count"] = state.retrieval_loop_count + 1

    return updates


def route_after_critique(state: MultiAgentState) -> Literal["retrieve", "synthesize"]:
    """Conditional edge — routing only, no state mutation (critique_node
    already updated plan/loop_count if it decided to loop back)."""
    verdict = state.critic_history[-1]
    if verdict.is_sufficient:
        return "synthesize"
    if state.retrieval_loop_count >= state.max_retrieval_loops:
        logger.warning("Max retrieval loops reached; synthesizing with best-effort context")
        return "synthesize"
    return "retrieve"


# ------------------------------------------------------------- Synthesizer

_SYNTHESIZER_SYSTEM_PROMPT = """You are the Synthesizer / Report Generator Agent. \
Compile the retrieved findings into a rigorous answer to the user's request, \
conforming exactly to this explainability contract: Detailed Response (full markdown-formatted answer for the user, cite chunk_ids inline in the detailed response so the frontend can eventually turn those into clickable source popovers); \
Reasoning Summary (explain HOW you reached your conclusions from the evidence — mandatory); \
Supporting Evidence (concrete claims, each traceable to a retrieved chunk id); \
Confidence (low/medium/high, justified by evidence coverage and any gaps the \
critic noted); References (chunk ids / parent_ids used); Related Reading \
(useful follow-up topics); Alternative Interpretations (only if evidence \
genuinely supports more than one reading — leave empty otherwise).
\n\nCRITICAL: Return ONLY raw JSON matching the required schema. Never wrap output in markdown fences, backticks, or '```json'.
"""

# WIP: Add detailed assistance response 
async def synthesize_node(state: MultiAgentState) -> dict:
    client = get_openai_client()
    settings = get_settings()

    context_blob = "\n\n".join(
        f"[step {sid}] query={res.query}\n{res.structured_context or '(no context retrieved)'}"
        for sid, res in state.step_results.items()
    )
    critic_summary = state.critic_history[-1].reasoning if state.critic_history else "N/A"
    user_content = (
        f"User request: {state.user_request}\n\nCritic's final assessment: {critic_summary}\n\n"
        f"Retrieved context:\n\n{context_blob}"
    )

    try:
        response = await client.responses.parse(
            model=settings.AGENT_SYNTHESIZER_MODEL,
            input=[
                {"role": "system", "content": _SYNTHESIZER_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            text_format=ExplainabilityReport,
        )
        report = response.output_parsed
        if report is None:
            raise ValueError("Synthesizer returned no parsed output")
    except _TRANSIENT_OPENAI_ERRORS:
        raise
    except Exception as exc:
        logger.exception("Synthesizer agent failed; producing a minimal degraded report")
        report = ExplainabilityReport(
            detailed_response="The system could not fully synthesize a report due to an internal error.",
            reasoning_summary=f"Synthesis failed: {exc}. Raw retrieved context is listed in references for manual review.",
            supporting_evidence=[],
            confidence="low",
            references=list(state.step_results.keys()),
            related_reading=[],
        )

    markdown = render_markdown_report(state, report)
    return {"report": report, "markdown_report": markdown, "status": AgentStatus.DONE}