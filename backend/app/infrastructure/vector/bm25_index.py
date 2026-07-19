from __future__ import annotations

import asyncio
import pickle
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from rank_bm25 import BM25Okapi

from app.core.config import get_settings
from app.knowledge.models import Chunk, ScoredChunk, SourceType


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


@dataclass
class _Bm25State:
    """Process-wide mutable state, guarded by `lock`. rank_bm25 has no
    incremental-update API — every insert rebuilds the full index, so
    mutation is always taken under the lock and off the event loop."""

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    chunks: dict[str, Chunk] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    bm25: BM25Okapi | None = None


@lru_cache
def get_bm25_state() -> _Bm25State:
    return _Bm25State()


class Bm25KeywordIndex:
    """KeywordIndexPort adapter over an in-memory BM25 index."""

    async def add_documents(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        state = get_bm25_state()
        async with state.lock:
            await asyncio.to_thread(self._add_documents_sync, state, chunks)
            await asyncio.to_thread(self._persist_sync, state)

    async def search(
        self,
        query: str,
        top_k: int,
        source_types: tuple[SourceType, ...] | None,
        metadata_filter: dict[str, Any] | None,
    ) -> list[ScoredChunk]:
        state = get_bm25_state()
        async with state.lock:
            if state.bm25 is None or not state.order:
                return []
            return await asyncio.to_thread(
                self._search_sync, state, query, top_k, source_types, metadata_filter
            )

    # --- sync internals; only ever called from a lock + worker thread ---

    @staticmethod
    def _add_documents_sync(state: _Bm25State, chunks: list[Chunk]) -> None:
        for chunk in chunks:
            if chunk.chunk_id not in state.chunks:
                state.order.append(chunk.chunk_id)
            state.chunks[chunk.chunk_id] = chunk
        tokenized = [_tokenize(state.chunks[cid].text) for cid in state.order]
        state.bm25 = BM25Okapi(tokenized)

    @staticmethod
    def _search_sync(
        state: _Bm25State,
        query: str,
        top_k: int,
        source_types: tuple[SourceType, ...] | None,
        metadata_filter: dict[str, Any] | None,
    ) -> list[ScoredChunk]:
        assert state.bm25 is not None
        scores = state.bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(state.order, scores), key=lambda pair: pair[1], reverse=True)

        results: list[ScoredChunk] = []
        for chunk_id, score in ranked:
            if score <= 0:
                continue
            chunk = state.chunks[chunk_id]
            if source_types and chunk.source_type not in source_types:
                continue
            if metadata_filter and not Bm25KeywordIndex._matches_filter(chunk, metadata_filter):
                continue
            results.append(ScoredChunk(chunk=chunk, score=float(score)))
            if len(results) >= top_k:
                break
        return results

    @staticmethod
    def _matches_filter(chunk: Chunk, metadata_filter: dict[str, Any]) -> bool:
        # Supports the common subset of Pinecone filter syntax we accept
        # from callers ($in + exact match). Extend if you need $gte etc.
        for key, expected in metadata_filter.items():
            if key == "source_type":
                continue  # handled separately via source_types param
            actual = chunk.metadata.get(key)
            if isinstance(expected, dict) and "$in" in expected:
                if actual not in expected["$in"]:
                    return False
            elif actual != expected:
                return False
        return True

    @staticmethod
    def _persist_sync(state: _Bm25State) -> None:
        settings = get_settings()
        path = settings.BM25_INDEX_PERSIST_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as f:
            pickle.dump({"chunks": state.chunks, "order": state.order}, f)

    @classmethod
    def load_from_disk(cls) -> None:
        """Call once at startup to restore the index across restarts."""
        settings = get_settings()
        path = settings.BM25_INDEX_PERSIST_PATH
        if not path.exists():
            return
        with path.open("rb") as f:
            data = pickle.load(f)
        state = get_bm25_state()
        state.chunks = data["chunks"]
        state.order = data["order"]
        if state.order:
            state.bm25 = BM25Okapi([_tokenize(state.chunks[cid].text) for cid in state.order])