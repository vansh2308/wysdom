from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Any

from app.core.config import get_settings


@lru_cache
def get_artifact_dict() -> dict[str, Any]:
    """
    Loads all marker/surya model weights once per process — this is the
    expensive part (multiple GB). Exactly like get_engine() for the DB:
    a process-wide singleton, created lazily on first use unless eager
    loading is enabled in bootstrap.
    """
    settings = get_settings()
    if settings.PDF_EXTRACTION_DEVICE:
        os.environ.setdefault("TORCH_DEVICE", settings.PDF_EXTRACTION_DEVICE)

    from marker.models import create_model_dict  # deferred: heavy torch init

    return create_model_dict()


@lru_cache
def get_extraction_executor() -> ThreadPoolExecutor:
    """
    marker's PdfConverter.__call__ is synchronous and CPU/GPU-bound, so it
    always runs here via loop.run_in_executor — never awaited directly.
    Sized conservatively: marker/surya inference uses ~3.5-5GB VRAM per
    concurrent conversion, so this pool intentionally throttles rather
    than maximizing throughput.
    """
    settings = get_settings()
    return ThreadPoolExecutor(
        max_workers=settings.PDF_EXTRACTION_WORKERS,
        thread_name_prefix="pdf-extraction",
    )


@lru_cache
def get_extraction_semaphore() -> asyncio.Semaphore:
    """Extra guard rail so queued requests can't pile up past pool capacity."""
    settings = get_settings()
    return asyncio.Semaphore(settings.PDF_EXTRACTION_MAX_CONCURRENCY)