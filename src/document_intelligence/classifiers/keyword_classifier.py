"""Keyword-based document classifier.

A lightweight, zero-model classifier that scores document text against the
keyword lists defined in ``config/document_types.yaml``.  It works in two
passes:

1. **Filename heuristic** -- certain filenames (e.g. ``rental_statement.pdf``)
   give an instant match.
2. **Content scoring** -- the first ~3 000 characters of extracted text are
   compared against each document type's keyword list using word-boundary
   matching. Multi-word phrases get higher weight. The type with the highest
   weighted score wins.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from document_intelligence.core.type_registry import DocumentTypeRegistry
from document_intelligence.models.documents import ClassificationResult, DocumentType

logger = logging.getLogger(__name__)

_SAMPLE_CHARS = 3000


def _build_pattern(keyword: str) -> re.Pattern[str]:
    """Build a word-boundary regex for a keyword."""
    escaped = re.escape(keyword)
    return re.compile(rf"\b{escaped}\b", re.IGNORECASE)


class KeywordClassifier:
    """Classify documents by keyword frequency analysis."""

    def __init__(
        self,
        registry: DocumentTypeRegistry,
        converter: Any | None = None,
    ) -> None:
        self._registry = registry
        self._converter = converter
        self._patterns: dict[str, list[tuple[re.Pattern[str], float]]] = {}
        self._build_patterns()

    def _build_patterns(self) -> None:
        """Pre-compile regex patterns with weights for each document type."""
        for cfg in self._registry.all_types():
            patterns: list[tuple[re.Pattern[str], float]] = []
            for kw in cfg.keywords:
                pattern = _build_pattern(kw)
                # Multi-word phrases are more discriminative — weight them higher.
                word_count = len(kw.split())
                weight = 1.0 + (word_count - 1) * 0.5
                patterns.append((pattern, weight))
            self._patterns[cfg.key] = patterns

    def set_converter(self, converter: Any) -> None:
        """Inject a pre-warmed DocumentConverter to avoid cold-start."""
        self._converter = converter

    def classify(self, file_path: Path) -> DocumentType:
        """Return the best-matching ``DocumentType`` for *file_path*."""
        result = self.classify_with_confidence(file_path)
        return result.document_type

    def classify_with_confidence(self, file_path: Path) -> ClassificationResult:
        """Classify and return full result with confidence scores."""

        # -- pass 1: filename --
        name_lower = file_path.stem.lower().replace("_", " ").replace("-", " ")
        for cfg in self._registry.all_types():
            for kw in cfg.keywords:
                if kw in name_lower:
                    logger.debug("Filename match: %s -> %s", file_path.name, cfg.key)
                    return ClassificationResult(
                        document_type=DocumentType(cfg.key),
                        confidence=0.9,
                        scores={cfg.key: 1.0},
                    )

        # -- pass 2: content sample with word-boundary matching --
        text = self._read_text_sample(file_path)
        if not text:
            logger.warning("Could not read text from %s; returning UNKNOWN.", file_path.name)
            return ClassificationResult(
                document_type=DocumentType.UNKNOWN,
                confidence=0.0,
                scores={},
            )

        scores: dict[str, float] = {}
        for cfg in self._registry.all_types():
            patterns = self._patterns.get(cfg.key, [])
            if not patterns:
                scores[cfg.key] = 0.0
                continue

            total_weight = sum(w for _, w in patterns)
            hit_weight = 0.0
            for pattern, weight in patterns:
                if pattern.search(text):
                    hit_weight += weight
            scores[cfg.key] = hit_weight / total_weight

        if not scores or max(scores.values()) == 0:
            return ClassificationResult(
                document_type=DocumentType.UNKNOWN,
                confidence=0.0,
                scores=scores,
            )

        best = max(scores, key=scores.get)  # type: ignore[arg-type]
        best_score = scores[best]

        # Confidence: based on separation from second-best.
        sorted_scores = sorted(scores.values(), reverse=True)
        second_best = sorted_scores[1] if len(sorted_scores) > 1 else 0.0
        if best_score > 0:
            separation = (best_score - second_best) / best_score
            confidence = min(0.5 + separation * 0.5, 1.0)
        else:
            confidence = 0.0

        logger.info(
            "Classification scores: %s -> winner: %s (confidence: %.2f)",
            {k: round(v, 3) for k, v in scores.items()},
            best,
            confidence,
        )

        try:
            doc_type = DocumentType(best)
        except ValueError:
            doc_type = DocumentType.UNKNOWN
            confidence = 0.0

        return ClassificationResult(
            document_type=doc_type,
            confidence=round(confidence, 3),
            scores={k: round(v, 3) for k, v in scores.items()},
        )

    # ------------------------------------------------------------------
    # Text sampling
    # ------------------------------------------------------------------

    def _read_text_sample(self, file_path: Path) -> str:
        """Extract a short text sample from the document."""
        suffix = file_path.suffix.lower()

        if suffix in (".txt", ".csv", ".md", ".html"):
            try:
                return file_path.read_text(encoding="utf-8", errors="replace")[:_SAMPLE_CHARS]
            except Exception:
                return ""

        if suffix in (".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".docx"):
            try:
                converter = self._get_converter()
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

    def _get_converter(self) -> Any:
        """Return shared converter or create one."""
        if self._converter is not None:
            return self._converter

        from docling.document_converter import DocumentConverter
        self._converter = DocumentConverter()
        return self._converter
