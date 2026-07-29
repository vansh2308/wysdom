from __future__ import annotations

import math
from functools import partial
from typing import Any


def _precision_at_k(inputs: dict, outputs: dict, reference_outputs: dict, k: int) -> dict[str, Any]:
    retrieved = outputs["retrieved_chunk_ids"][:k]
    expected = set(reference_outputs["expected_chunk_ids"])
    if not retrieved:
        return {"key": f"precision@{k}", "score": 0.0}
    hits = sum(1 for cid in retrieved if cid in expected)
    return {"key": f"precision@{k}", "score": hits / len(retrieved)}


def _recall_at_k(inputs: dict, outputs: dict, reference_outputs: dict, k: int) -> dict[str, Any]:
    retrieved = set(outputs["retrieved_chunk_ids"][:k])
    expected = reference_outputs["expected_chunk_ids"]
    if not expected:
        return {"key": f"recall@{k}", "score": None}
    hits = sum(1 for cid in expected if cid in retrieved)
    return {"key": f"recall@{k}", "score": hits / len(expected)}


def _hit_rate_at_k(inputs: dict, outputs: dict, reference_outputs: dict, k: int) -> dict[str, Any]:
    retrieved = set(outputs["retrieved_chunk_ids"][:k])
    expected = set(reference_outputs["expected_chunk_ids"])
    return {"key": f"hit_rate@{k}", "score": 1.0 if retrieved & expected else 0.0}


def _ndcg_at_k(inputs: dict, outputs: dict, reference_outputs: dict, k: int) -> dict[str, Any]:
    """Binary relevance nDCG — every expected chunk_id has relevance=1.
    Graded relevance would need a richer dataset schema (a score per
    expected id, not just a set) if you want that later."""
    retrieved = outputs["retrieved_chunk_ids"][:k]
    expected = set(reference_outputs["expected_chunk_ids"])
    dcg = sum(1.0 / math.log2(i + 2) for i, cid in enumerate(retrieved) if cid in expected)
    ideal_hits = min(len(expected), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return {"key": f"ndcg@{k}", "score": dcg / idcg if idcg > 0 else 0.0}


def retrieval_evaluators(ks: list[int]) -> list:
    """One evaluator per (metric, k) pair — LangSmith's aevaluate accepts a
    flat list, each returning its own named {key, score}."""
    evaluators = []
    for k in ks:
        evaluators.append(partial(_precision_at_k, k=k))
        evaluators.append(partial(_recall_at_k, k=k))
        evaluators.append(partial(_hit_rate_at_k, k=k))
        evaluators.append(partial(_ndcg_at_k, k=k))
    return evaluators