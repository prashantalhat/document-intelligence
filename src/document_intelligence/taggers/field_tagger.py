"""Semantic field tagger.

Maps raw extracted field keys to canonical semantic tags using the alias
mappings in ``config/document_types.yaml``.

The matching algorithm:

1. Exact match (case-insensitive).
2. Substring containment (the alias appears in the raw key or vice-versa).
3. Token overlap (Jaccard similarity on word tokens).

Fields that cannot be matched keep their original key as the semantic tag
with a lowered confidence score.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from document_intelligence.core.type_registry import DocumentTypeRegistry
from document_intelligence.models.documents import (
    DocumentType,
    ExtractedField,
    ExtractionResult,
    TaggedField,
)

logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[a-z0-9]+")


class FieldTagger:
    """Tag extracted fields with semantic labels."""

    def __init__(self, registry: DocumentTypeRegistry) -> None:
        self._registry = registry

    def tag(self, extraction: ExtractionResult) -> list[TaggedField]:
        """Tag every field in *extraction* and return ``TaggedField`` objects."""
        aliases = self._registry.field_aliases(extraction.document_type)
        if not aliases:
            # No alias map -- pass fields through with their raw keys.
            return [
                TaggedField(
                    semantic_tag=self._normalise_key(f.key),
                    raw_key=f.key,
                    value=f.value,
                    normalised_value=self._normalise_value(f.value),
                    confidence=f.confidence * 0.5,
                    page=f.page,
                )
                for f in extraction.fields
            ]

        tagged: list[TaggedField] = []
        for field in extraction.fields:
            tag, score = self._best_match(field.key, aliases)
            tagged.append(
                TaggedField(
                    semantic_tag=tag,
                    raw_key=field.key,
                    value=field.value,
                    normalised_value=self._normalise_value(field.value),
                    confidence=round(field.confidence * score, 4),
                    page=field.page,
                )
            )
        return tagged

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    def _best_match(
        self,
        raw_key: str,
        aliases: dict[str, list[str]],
    ) -> tuple[str, float]:
        """Return ``(semantic_tag, match_quality)`` for *raw_key*.

        *match_quality* is in ``[0, 1]`` and multiplied with the field's
        own confidence to produce the final score.
        """
        key_lower = raw_key.strip().lower()
        key_tokens = set(_WORD_RE.findall(key_lower))

        best_tag = self._normalise_key(raw_key)
        best_score = 0.3  # default for unmatched fields

        for tag, alias_list in aliases.items():
            for alias in alias_list:
                # exact
                if key_lower == alias:
                    return tag, 1.0
                # substring
                if alias in key_lower or key_lower in alias:
                    score = 0.85
                    if score > best_score:
                        best_tag, best_score = tag, score
                    continue
                # token overlap (Jaccard)
                alias_tokens = set(_WORD_RE.findall(alias))
                if alias_tokens and key_tokens:
                    jaccard = len(alias_tokens & key_tokens) / len(alias_tokens | key_tokens)
                    if jaccard > 0.5 and jaccard > best_score:
                        best_tag, best_score = tag, round(jaccard, 4)

        return best_tag, best_score

    # ------------------------------------------------------------------
    # Normalisation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_key(raw: str) -> str:
        """Turn an arbitrary key string into a snake_case tag."""
        s = raw.strip().lower()
        s = re.sub(r"[^a-z0-9]+", "_", s)
        return s.strip("_")

    @staticmethod
    def _normalise_value(value: Any) -> Any:
        """Best-effort normalisation (strip currency symbols, parse numbers)."""
        if not isinstance(value, str):
            return value

        cleaned = value.strip()

        # Currency: "$1,500.00" -> 1500.00
        money_match = re.match(
            r"^[£$€¥]?\s*([\d,]+\.?\d*)\s*$",
            cleaned,
        )
        if money_match:
            try:
                return float(money_match.group(1).replace(",", ""))
            except ValueError:
                pass

        # Percentage: "15%" -> 15.0
        pct_match = re.match(r"^([\d.]+)\s*%$", cleaned)
        if pct_match:
            try:
                return float(pct_match.group(1))
            except ValueError:
                pass

        return cleaned
