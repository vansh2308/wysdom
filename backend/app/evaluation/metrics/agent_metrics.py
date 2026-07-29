from __future__ import annotations

from typing import Any


def critic_loop_count(inputs: dict, outputs: dict, reference_outputs: dict | None = None) -> dict[str, Any]:
    return {"key": "critic_loop_count", "score": outputs.get("retrieval_loop_count", 0)}


def dag_parallelism(inputs: dict, outputs: dict, reference_outputs: dict | None = None) -> dict[str, Any]:
    """Ratio of steps that had zero dependencies (i.e. could run in the
    first wave, in parallel) to total steps — a crude but cheap signal for
    whether the planner is actually exploiting parallelism or defaulting
    to a sequential chain."""
    plan = outputs.get("plan")
    if not plan or not plan.get("steps"):
        return {"key": "dag_parallelism", "score": None}
    steps = plan["steps"]
    parallel_eligible = sum(1 for s in steps if not s.get("depends_on"))
    return {"key": "dag_parallelism", "score": parallel_eligible / len(steps)}


def fallback_triggered(inputs: dict, outputs: dict, reference_outputs: dict | None = None) -> dict[str, Any]:
    return {"key": "fallback_triggered", "score": 1.0 if outputs.get("errors") else 0.0}


def guardrail_clean_pass(inputs: dict, outputs: dict, reference_outputs: dict | None = None) -> dict[str, Any]:
    findings = outputs.get("guardrail_findings", [])
    blocked = [f for f in findings if f.get("severity") == "block"]
    return {"key": "guardrail_clean_pass", "score": 0.0 if blocked else 1.0}


def agent_evaluators() -> list:
    return [critic_loop_count, dag_parallelism, fallback_triggered, guardrail_clean_pass]