"""Keyword-based document classifier.

A lightweight, zero-model classifier that scores document text against the
keyword lists defined in ``config/document_types.yaml``.  It works in two
passes:

1. **Filename heuristic** -- certain filenames (e.g. ``rental_statement.pdf``)
   give an instant match.
2. **Content scoring** -- the first ~3 000 characters of extracted text are
   compared against each document type's keyword list.  The type with the
   highest normalised hit count wins.

This classifier is intentionally simple. A future ML-based classifier can
replace it by implementing the same interface.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from document_intelligence.core.type_registry import DocumentTypeRegistry
from document_intelligence.models.documents import DocumentType

logger = logging.getLogger(__name__)

# How many characters from the beginning of the file to use for scoring.
_SAMPLE_CHARS = 3000


class KeywordClassifier:
    """Classify documents by keyword frequency analysis."""

    def __init__(self, registry: DocumentTypeRegistry) -> None:
        self._registry = registry

    def classify(self, file_path: Path) -> DocumentType:
        """Return the best-matching ``DocumentType`` for *file_path*."""

        # -- pass 1: filename --
        name_lower = file_path.stem.lower().replace("_", " ").replace("-", " ")
        for cfg in self._registry.all_types():
            for kw in cfg.keywords:
                if kw in name_lower:
                    logger.debug("Filename match: %s -> %s", file_path.name, cfg.key)
                    return DocumentType(cfg.key)

        # -- pass 2: content sample --
        text = self._read_text_sample(file_path)
        if not text:
            logger.warning("Could not read text from %s; returning UNKNOWN.", file_path.name)
            return DocumentType.UNKNOWN

        scores: dict[str, float] = {}
        text_lower = text.lower()
        for cfg in self._registry.all_types():
            hits = sum(1 for kw in cfg.keywords if kw in text_lower)
            # Normalise by keyword count to avoid bias towards types with
            # many keywords.
            scores[cfg.key] = hits / max(len(cfg.keywords), 1)

        if not scores or max(scores.values()) == 0:
            return DocumentType.UNKNOWN

        best = max(scores, key=scores.get)  # type: ignore[arg-type]
        logger.info(
            "Content classification scores: %s  -> winner: %s",
            {k: round(v, 3) for k, v in scores.items()},
            best,
        )
        try:
            return DocumentType(best)
        except ValueError:
            return DocumentType.UNKNOWN

    # ------------------------------------------------------------------
    # Text sampling
    # ------------------------------------------------------------------

    @staticmethod
    def _read_text_sample(file_path: Path) -> str:
        """Extract a short text sample from the document.

        For PDFs we use Docling (already a dependency). For plain text
        and simple formats we read bytes directly.
        """
        suffix = file_path.suffix.lower()

        if suffix in (".txt", ".csv", ".md", ".html"):
            try:
                return file_path.read_text(encoding="utf-8", errors="replace")[:_SAMPLE_CHARS]
            except Exception:
                return ""

        if suffix in (".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".docx"):
            try:
                from docling.document_converter import DocumentConverter

                converter = DocumentConverter()
                result = converter.convert(str(file_path))
                md = result.document.export_to_markdown()
                return md[:_SAMPLE_CHARS]
            except Exception:
                logger.warning(
                    "Docling conversion failed during classification for %s",
                    file_path.name,
                    exc_info=True,
                )
                return ""

        return ""
