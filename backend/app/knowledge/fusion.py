from __future__ import annotations


def reciprocal_rank_fusion(
    ranked_id_lists: list[list[str]], k: int = 60
) -> dict[str, float]:
    """
    score(d) = sum_i 1 / (k + rank_i(d)) across every ranked list d appears
    in. Lists are best-first (rank 1 = most relevant). Pure function, no
    infra dependencies, unit-testable on its own.
    """
    scores: dict[str, float] = {}
    for ranked_ids in ranked_id_lists:
        for rank, chunk_id in enumerate(ranked_ids, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return scores