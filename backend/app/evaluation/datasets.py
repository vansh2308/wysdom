
from __future__ import annotations

import logging

from app.infrastructure.observability.langsmith_client import get_langsmith_client

logger = logging.getLogger(__name__)


async def ensure_dataset(name: str, examples: list[dict]) -> str:
    """Idempotent-ish seeding helper: creates the dataset if it doesn't
    exist yet, adds examples if it's currently empty. Dataset curation
    itself (choosing good queries/expected chunk_ids/rubrics) is inherently
    manual — this just handles the upload mechanics.
    """
    client = get_langsmith_client()
    try:
        dataset = client.read_dataset(dataset_name=name)
    except Exception:
        dataset = client.create_dataset(name)
        logger.info("Created LangSmith dataset %s", name)

    existing = list(client.list_examples(dataset_id=dataset.id, limit=1))
    if not existing:
        client.create_examples(dataset_name=name, examples=examples)
        logger.info("Seeded %d examples into dataset %s", len(examples), name)
    return dataset.name