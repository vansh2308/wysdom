
from __future__ import annotations

import logging

from fastapi import APIRouter, Form, HTTPException, UploadFile, status

from app.api.dependencies import PdfExtraction

from app.documents.models import PdfExtractionResponse, ExtractionOptions, ExtractionOutputFormat
from app.documents.pdf_extraction_service import FileTooLargeError, UnsupportedFileError
from app.infrastructure.documents.marker_extractor import MarkerExtractionError


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/extract", response_model=PdfExtractionResponse)
async def extract_pdf(
    service: PdfExtraction,
    file: UploadFile,
    output_format: ExtractionOutputFormat = Form(default=ExtractionOutputFormat.JSON),
    use_llm: bool = Form(default=False),
    force_ocr: bool = Form(default=False),
    extract_images: bool = Form(default=True),
    page_range: str | None = Form(default=None),
) -> PdfExtractionResponse:
    options = ExtractionOptions(
        output_format=output_format,
        use_llm=use_llm,
        force_ocr=force_ocr,
        extract_images=extract_images,
        page_range=page_range,
    )

    try:
        result = await service.extract_from_upload(file, options)
    except (UnsupportedFileError, FileTooLargeError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except MarkerExtractionError as exc:
        logger.exception("PDF extraction failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail="PDF extraction failed."
        ) from exc

    return PdfExtractionResponse(
        source_filename=result.source_filename,
        output_format=result.output_format,
        page_count=result.page_count,
        content=result.content,
        markdown=result.markdown,
        images=result.images,
        metadata=result.metadata,
    )