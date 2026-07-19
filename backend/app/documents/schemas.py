

from pydantic import BaseModel, Field
from typing import Any

from app.documents.models import ExtractionOutputFormat

class PdfExtractionResponse(BaseModel):
    source_filename: str
    output_format: ExtractionOutputFormat
    page_count: int
    content: dict[str, Any] | str
    markdown: str | None = None
    images: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)