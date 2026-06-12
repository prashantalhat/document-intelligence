"""Main document processing pipeline.

Orchestrates: ingest -> classify -> extract -> tag -> format.
Each stage is pluggable through the registry / strategy pattern so new
document types and extraction engines can be added without modifying
existing code.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import BinaryIO

from document_intelligence.classifiers.keyword_classifier import KeywordClassifier
from document_intelligence.config.settings import Settings, get_settings
from document_intelligence.core.type_registry import DocumentTypeRegistry
from document_intelligence.extractors.base import BaseExtractor
from document_intelligence.extractors.docling_extractor import DoclingExtractor
from document_intelligence.formatters.json_formatter import JsonFormatter
from document_intelligence.formatters.csv_formatter import CsvFormatter
from document_intelligence.models.documents import (
    DocumentMetadata,
    DocumentType,
    ExtractionResult,
    ProcessingResult,
    ProcessingStatus,
)
from document_intelligence.taggers.field_tagger import FieldTagger

logger = logging.getLogger(__name__)


class DocumentPipeline:
    """End-to-end document processing pipeline.

    Usage::

        pipeline = DocumentPipeline()
        result = pipeline.process("path/to/document.pdf")
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._type_registry = DocumentTypeRegistry()
        self._classifier = KeywordClassifier(self._type_registry)
        self._extractor = self._build_extractor()
        self._tagger = FieldTagger(self._type_registry)
        self._json_formatter = JsonFormatter()
        self._csv_formatter = CsvFormatter()

        # Ensure storage directories exist.
        self._settings.upload_dir.mkdir(parents=True, exist_ok=True)
        self._settings.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self,
        file_path: str | Path,
        *,
        document_type: DocumentType | None = None,
    ) -> ProcessingResult:
        """Run the full pipeline on a single document.

        Parameters
        ----------
        file_path:
            Path to the document file on disk.
        document_type:
            If provided, skip the classification stage and use this type
            directly. Useful when the caller already knows the doc type.

        Returns
        -------
        ProcessingResult
            The fully-processed, tagged output.
        """
        start = time.perf_counter()
        errors: list[str] = []
        path = Path(file_path)

        # -- 1. Ingest --------------------------------------------------
        logger.info("Ingesting document: %s", path.name)
        metadata = self._ingest(path)

        # -- 2. Classify -------------------------------------------------
        if document_type is None:
            logger.info("Classifying document: %s", metadata.document_id)
            document_type = self._classifier.classify(path)
            logger.info("Classified as: %s", document_type.value)
        else:
            logger.info("Document type provided: %s", document_type.value)

        # -- 3. Extract --------------------------------------------------
        logger.info("Extracting fields from: %s", metadata.document_id)
        try:
            extraction = self._extractor.extract(path, document_type)
        except Exception as exc:
            logger.exception("Extraction failed for %s", metadata.document_id)
            errors.append(f"Extraction error: {exc}")
            extraction = ExtractionResult(
                document_id=metadata.document_id,
                document_type=document_type,
            )

        # -- 4. Tag ------------------------------------------------------
        logger.info("Tagging fields for: %s", metadata.document_id)
        tagged = self._tagger.tag(extraction)

        # -- 5. Assemble result -----------------------------------------
        duration_ms = (time.perf_counter() - start) * 1000
        result = ProcessingResult(
            document_id=metadata.document_id,
            metadata=metadata,
            document_type=document_type,
            status=ProcessingStatus.COMPLETED if not errors else ProcessingStatus.FAILED,
            tagged_fields=tagged,
            tables=extraction.tables,
            raw_text=extraction.raw_text,
            raw_markdown=extraction.raw_markdown,
            errors=errors,
            processing_duration_ms=round(duration_ms, 2),
        )

        logger.info(
            "Completed %s in %.1f ms  (%d fields, %d errors)",
            metadata.document_id,
            duration_ms,
            len(tagged),
            len(errors),
        )
        return result

    def process_to_json(
        self,
        file_path: str | Path,
        *,
        document_type: DocumentType | None = None,
    ) -> str:
        """Process and return a JSON string."""
        result = self.process(file_path, document_type=document_type)
        return self._json_formatter.format(result)

    def process_to_csv(
        self,
        file_path: str | Path,
        *,
        document_type: DocumentType | None = None,
    ) -> str:
        """Process and return CSV text."""
        result = self.process(file_path, document_type=document_type)
        return self._csv_formatter.format(result)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _ingest(self, path: Path) -> DocumentMetadata:
        """Build metadata for an incoming file."""
        stat = path.stat()
        mime = self._guess_mime(path)
        return DocumentMetadata(
            filename=path.name,
            file_path=str(path.resolve()),
            file_size_bytes=stat.st_size,
            mime_type=mime,
        )

    def _build_extractor(self) -> BaseExtractor:
        """Instantiate the configured extraction engine."""
        engine = self._settings.extraction_engine
        if engine == "docling":
            return DoclingExtractor(self._settings, self._type_registry)
        # Future: add chandra, azure, etc.
        raise ValueError(f"Unknown extraction engine: {engine}")

    @staticmethod
    def _guess_mime(path: Path) -> str:
        suffix = path.suffix.lower()
        mapping = {
            ".pdf": "application/pdf",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".tiff": "image/tiff",
            ".tif": "image/tiff",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        return mapping.get(suffix, "application/octet-stream")
