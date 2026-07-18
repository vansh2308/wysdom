from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ExtractionOutputFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"
    CHUNKS = "chunks"
    HTML = "html"


@dataclass(frozen=True, slots=True)
class ExtractionOptions:
    output_format: ExtractionOutputFormat = ExtractionOutputFormat.CHUNKS
    use_llm: bool = False
    force_ocr: bool = False
    extract_images: bool = True
    page_range: str | None = None  # e.g. "0,5-10,20"


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    source_filename: str
    output_format: ExtractionOutputFormat
    content: dict[str, Any] | str
    markdown: str | None
    images: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    page_count: int = 0



class PdfExtractionResponse(BaseModel):
    source_filename: str
    output_format: ExtractionOutputFormat
    page_count: int
    content: dict[str, Any] | str
    markdown: str | None = None
    images: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)