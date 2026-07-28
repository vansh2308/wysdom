from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, List
from uuid import uuid4
from app.core.config import get_settings
from app.documents.models import ExtractionOptions, ExtractionOutputFormat, ExtractionResult
from app.infrastructure.documents.model_registry import get_artifact_dict, get_extraction_executor, get_extraction_semaphore

logger = logging.getLogger(__name__)


class MarkerExtractionError(RuntimeError):
    """Raised when marker fails to convert a document."""


class MarkerPdfExtractor:
    """
    Infrastructure adapter implementing PdfExtractorPort with `marker-pdf`.
    Stateless and cheap to construct per request — the actual heavy state
    (model weights, thread pool, semaphore) lives in module-level
    lru_cache singletons in model_registry.
    """

    
    blackListedBlockTypes: List[str]  = [
        "PageFooter"
    ]

    async def extract(
        self, file_path: Path, options: ExtractionOptions
    ) -> ExtractionResult:
        semaphore = get_extraction_semaphore()
        async with semaphore:
            loop = asyncio.get_running_loop()
            try:
                rendered = await loop.run_in_executor(
                    get_extraction_executor(),
                    self._convert_sync,
                    file_path,
                    options,
                )
            except Exception as exc:
                logger.exception("marker extraction failed for %s", file_path.name)
                raise MarkerExtractionError(str(exc)) from exc

        return self._to_domain_result(file_path.name, options, rendered)

    # --- blocking work, executed off the event loop ---

    @staticmethod
    def _convert_sync(file_path: Path, options: ExtractionOptions) -> Any:
        from marker.config.parser import ConfigParser
        from marker.converters.pdf import PdfConverter

        settings = get_settings()

        config: dict[str, Any] = {
            "output_format": options.output_format.value,
            "use_llm": options.use_llm,
            "force_ocr": options.force_ocr,
            "disable_image_extraction": not options.extract_images,
        }
        if options.page_range:
            config["page_range"] = options.page_range
        if settings.PDF_EXTRACTION_LLM_SERVICE:
            config["llm_service"] = settings.PDF_EXTRACTION_LLM_SERVICE

        config_parser = ConfigParser(config)
        converter = PdfConverter(
            config=config_parser.generate_config_dict(),
            artifact_dict=get_artifact_dict(),
            processor_list=config_parser.get_processors(),
            renderer=config_parser.get_renderer(),
            llm_service=config_parser.get_llm_service() if options.use_llm else None,
        )
        return converter(str(file_path))

    # --- map marker's rendered pydantic model -> our domain model ---
    
    @staticmethod
    def _to_domain_result(
        source_filename: str, options: ExtractionOptions, rendered: Any
    ) -> ExtractionResult:
        from marker.output import text_from_rendered

        payload = rendered.model_dump(mode="json")
        metadata_raw: dict[str, Any] = payload.get("metadata", {}) or {}

        markdown_text: str | None = None
        if options.output_format is ExtractionOutputFormat.MARKDOWN:
            markdown_text, _, image_dict = text_from_rendered(rendered)
            images = image_dict or {}
            content: dict[str, Any] | str = markdown_text or ""
        else:
            images = payload.get("images", {}) or {}
            content = payload  # tree (json), flat list (chunks), or html string

        page_stats = metadata_raw.get("page_stats", []) or []

        def getPageNoFromId(id: str):
            result: int = -1
            try:
                result = int(id.split("/")[2])
            except Exception as e:
                logger.info(id)
            finally:
                return result

        content['blocks'] = [{
            # "chunk_id": block.get("id"),
            "chunk_id": uuid4().hex,
            "block_type": block.get("block_type"),
            "text": block.get("html"),
            "metadata": {
                "page": getPageNoFromId(block.get("id")),
                # "bbox": block.get("bbox"),
                # "section_hierarchy": block.get('section_hierarchy')
            }
        } for block in content.get("blocks", []) if block.get('block_type') not in MarkerPdfExtractor.blackListedBlockTypes]

        return ExtractionResult(
            source_filename=source_filename,
            output_format=options.output_format,
            content=content,
            markdown=markdown_text,
            images=images if options.extract_images else {},
            metadata={
                "table_of_contents": metadata_raw.get("table_of_contents", []),
                "page_stats": page_stats,
            },
            page_count=len(page_stats),
        )