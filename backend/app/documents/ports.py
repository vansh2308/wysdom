
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.documents.models import ExtractionOptions, ExtractionResult


class PdfExtractorPort(Protocol):
    """
    Domain contract for semantic PDF extraction. The application layer
    depends only on this Protocol — never on marker directly — so the
    extraction engine can be swapped without touching business logic.
    """

    async def extract(
        self, file_path: Path, options: ExtractionOptions
    ) -> ExtractionResult: ...