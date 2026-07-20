
from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import get_settings
from app.documents.models import ExtractionOptions, ExtractionResult
from app.documents.ports import PdfExtractorPort

logger = logging.getLogger(__name__)


class UnsupportedFileError(ValueError):
    pass


class FileTooLargeError(ValueError):
    pass


# WIP: Exclude Page Footer 
class PdfExtractionService:
    """
    Orchestration only: validate → stage to disk → delegate to the domain
    port → guarantee cleanup. No marker-specific or HTTP-specific knowledge.
    """

    def __init__(self, extractor: PdfExtractorPort) -> None:
        self._extractor = extractor

    async def extract_from_upload(
        self, upload: UploadFile, options: ExtractionOptions
    ) -> ExtractionResult:
        self._validate_upload(upload)

        settings = get_settings()
        settings.PDF_EXTRACTION_TEMP_DIR.mkdir(parents=True, exist_ok=True)
        temp_path = settings.PDF_EXTRACTION_TEMP_DIR / f"{uuid.uuid4().hex}.pdf"

        try:
            await self._stage_file(
                upload, temp_path, settings.PDF_EXTRACTION_MAX_FILE_SIZE_MB
            )
            return await self._extractor.extract(temp_path, options)
        finally:
            temp_path.unlink(missing_ok=True)

    def _validate_upload(self, upload: UploadFile) -> None:
        if upload.content_type not in {"application/pdf", "application/octet-stream"}:
            raise UnsupportedFileError(
                f"Unsupported content type: {upload.content_type!r}. Expected a PDF."
            )
        if not (upload.filename or "").lower().endswith(".pdf"):
            raise UnsupportedFileError("File must have a .pdf extension.")

    @staticmethod
    async def _stage_file(upload: UploadFile, dest: Path, max_size_mb: int) -> None:
        max_bytes = max_size_mb * 1024 * 1024
        written = 0
        with dest.open("wb") as f:
            while chunk := await upload.read(1024 * 1024):
                written += len(chunk)
                if written > max_bytes:
                    dest.unlink(missing_ok=True)
                    raise FileTooLargeError(f"File exceeds the {max_size_mb}MB limit.")
                f.write(chunk)
        await upload.seek(0)