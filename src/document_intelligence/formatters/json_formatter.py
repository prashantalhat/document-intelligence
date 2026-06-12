"""JSON output formatter."""

from __future__ import annotations

import json
from typing import Any

from document_intelligence.models.documents import ProcessingResult


class JsonFormatter:
    """Format a ``ProcessingResult`` as a clean JSON document."""

    def format(self, result: ProcessingResult) -> str:
        """Return a pretty-printed JSON string."""
        payload = self._build_payload(result)
        return json.dumps(payload, indent=2, default=str, ensure_ascii=False)

    def format_dict(self, result: ProcessingResult) -> dict[str, Any]:
        """Return the payload as a plain dict (useful for API responses)."""
        return self._build_payload(result)

    # ------------------------------------------------------------------

    @staticmethod
    def _build_payload(result: ProcessingResult) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        for tf in result.tagged_fields:
            fields[tf.semantic_tag] = {
                "value": tf.normalised_value if tf.normalised_value is not None else tf.value,
                "raw_value": tf.value,
                "confidence": tf.confidence,
                "page": tf.page,
            }

        return {
            "document_id": result.document_id,
            "document_type": result.document_type.value,
            "status": result.status.value,
            "metadata": {
                "filename": result.metadata.filename,
                "file_size_bytes": result.metadata.file_size_bytes,
                "mime_type": result.metadata.mime_type,
                "page_count": result.metadata.page_count,
                "ingested_at": result.metadata.ingested_at.isoformat(),
            },
            "fields": fields,
            "tables": result.tables,
            "errors": result.errors,
            "processing_duration_ms": result.processing_duration_ms,
            "processed_at": result.processed_at.isoformat(),
        }
