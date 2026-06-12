"""Docling-based extraction engine.

Uses IBM Docling for:
- PDF / image / DOCX conversion to structured markdown and tables
- Optional structured extraction via Pydantic schemas
  (requires the NuExtract model, gated behind ``docling[extract]``)

The extractor operates in two phases:

1. **Conversion** -- full document to markdown + tables via
   ``DocumentConverter``.
2. **Structured extraction** (optional) -- if a Pydantic schema is
   registered for the document type, ``DocumentExtractor`` pulls typed
   fields directly.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from document_intelligence.config.settings import Settings, get_settings
from document_intelligence.core.type_registry import DocumentTypeRegistry
from document_intelligence.extractors.base import BaseExtractor
from document_intelligence.models.documents import (
    DocumentType,
    ExtractedField,
    ExtractionResult,
)

logger = logging.getLogger(__name__)

# Supported MIME types for Docling.
_SUPPORTED_MIMES = frozenset(
    {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/tiff",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/html",
    }
)


class DoclingExtractor(BaseExtractor):
    """Extraction engine backed by IBM Docling."""

    def __init__(
        self,
        settings: Settings | None = None,
        type_registry: DocumentTypeRegistry | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._registry = type_registry or DocumentTypeRegistry()

        # Lazy-loaded Docling objects (heavy imports).
        self._converter: Any | None = None
        self._doc_extractor: Any | None = None

    # ------------------------------------------------------------------
    # BaseExtractor interface
    # ------------------------------------------------------------------

    def extract(self, file_path: Path, document_type: DocumentType) -> ExtractionResult:
        converter = self._get_converter()
        doc_result = converter.convert(str(file_path))
        document = doc_result.document

        raw_md = document.export_to_markdown()
        raw_text = self._markdown_to_plain(raw_md)
        tables = self._extract_tables(document)

        # Try structured extraction from already-converted document first,
        # only fall back to re-reading file if schema requires it.
        fields = self._structured_extract(document, file_path, document_type, raw_md)

        return ExtractionResult(
            document_id="",  # filled by pipeline
            document_type=document_type,
            fields=fields,
            tables=tables,
            raw_text=raw_text,
            raw_markdown=raw_md,
            extraction_engine="docling",
        )

    def warm_up(self) -> None:
        """Eagerly initialize heavy ML models."""
        self._get_converter()

    def supports_format(self, mime_type: str) -> bool:
        return mime_type in _SUPPORTED_MIMES

    # ------------------------------------------------------------------
    # Docling conversion
    # ------------------------------------------------------------------

    def _get_converter(self) -> Any:
        """Lazy-initialise the Docling ``DocumentConverter``."""
        if self._converter is not None:
            return self._converter

        from docling.document_converter import DocumentConverter

        self._converter = DocumentConverter()
        logger.info("Docling DocumentConverter initialised.")
        return self._converter

    # ------------------------------------------------------------------
    # Table extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_tables(document: Any) -> list[list[list[str]]]:
        """Pull all tables from a DoclingDocument as 2-D string arrays."""
        tables: list[list[list[str]]] = []
        try:
            for table in document.tables:
                grid: list[list[str]] = []
                if hasattr(table, "export_to_dataframe"):
                    df = table.export_to_dataframe()
                    # header row
                    grid.append(list(df.columns))
                    for _, row in df.iterrows():
                        grid.append([str(v) for v in row.values])
                elif hasattr(table, "data"):
                    for row in table.data:
                        grid.append([str(cell) for cell in row])
                if grid:
                    tables.append(grid)
        except Exception:
            logger.warning("Table extraction encountered an error; continuing.", exc_info=True)
        return tables

    # ------------------------------------------------------------------
    # Structured extraction
    # ------------------------------------------------------------------

    def _structured_extract(
        self,
        document: Any,
        file_path: Path,
        document_type: DocumentType,
        raw_markdown: str,
    ) -> list[ExtractedField]:
        """Attempt schema-based extraction using the already-converted document.

        Falls back to regex if the extraction extra is not installed.
        """
        type_cfg = self._registry.get(document_type)
        if type_cfg is None:
            return []

        schema_cls = type_cfg.get_schema_class()
        if schema_cls is None:
            return []

        try:
            from docling.document_extractor import DocumentExtractor

            extractor = self._get_doc_extractor()
            # Pass pre-converted document to avoid re-reading file from disk.
            if hasattr(extractor, "extract_from_document"):
                result = extractor.extract_from_document(document=document, template=schema_cls)
            else:
                result = extractor.extract(source=str(file_path), template=schema_cls)

            fields: list[ExtractedField] = []
            for page_idx, page in enumerate(result.pages):
                data: dict[str, Any] = page.extracted_data if hasattr(page, "extracted_data") else {}
                for key, value in data.items():
                    if value is None:
                        continue
                    fields.append(
                        ExtractedField(
                            key=key,
                            value=value,
                            confidence=0.85,
                            page=page_idx + 1,
                        )
                    )
            return fields

        except ImportError:
            logger.info(
                "docling.document_extractor not available; "
                "install docling[extract] for structured extraction. "
                "Falling back to markdown-only output."
            )
            return self._fallback_regex_extract(raw_markdown, document_type)
        except Exception:
            logger.warning(
                "Structured extraction failed; falling back to regex.",
                exc_info=True,
            )
            return self._fallback_regex_extract(raw_markdown, document_type)

    def _get_doc_extractor(self) -> Any:
        if self._doc_extractor is not None:
            return self._doc_extractor

        from docling.datamodel.base_models import InputFormat
        from docling.document_extractor import DocumentExtractor

        self._doc_extractor = DocumentExtractor(
            allowed_formats=[InputFormat.PDF, InputFormat.IMAGE],
        )
        return self._doc_extractor

    # ------------------------------------------------------------------
    # Fallback regex extraction
    # ------------------------------------------------------------------

    def _fallback_regex_extract(
        self,
        markdown: str,
        document_type: DocumentType,
    ) -> list[ExtractedField]:
        """Best-effort key-value extraction from markdown when the structured
        extraction extra is not installed.

        Looks for lines matching ``Key: Value`` or ``Key | Value`` patterns
        and returns them as raw extracted fields.
        """
        import re

        fields: list[ExtractedField] = []
        # Match lines like "Tenant Name: Jane Doe" or "Rent Amount | $1,500.00"
        pattern = re.compile(
            r"^[#*\s]*(?P<key>[A-Za-z][A-Za-z0-9 _/\-]{1,60})\s*[:|\t]+\s*(?P<value>.+)$",
            re.MULTILINE,
        )
        for match in pattern.finditer(markdown):
            key = match.group("key").strip()
            value = match.group("value").strip()
            if value:
                fields.append(
                    ExtractedField(key=key, value=value, confidence=0.5)
                )
        logger.info("Fallback regex extracted %d fields.", len(fields))
        return fields

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _markdown_to_plain(md: str) -> str:
        """Rough markdown-to-plain-text conversion."""
        import re
        text = re.sub(r"[#*`>|]", "", md)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
