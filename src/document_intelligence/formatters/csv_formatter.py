"""CSV output formatter."""

from __future__ import annotations

import csv
import io

from document_intelligence.models.documents import ProcessingResult


class CsvFormatter:
    """Format a ``ProcessingResult`` as CSV text.

    Each row is one tagged field:

        document_id, document_type, semantic_tag, value, raw_value, confidence, page
    """

    HEADER = [
        "document_id",
        "document_type",
        "semantic_tag",
        "value",
        "raw_value",
        "confidence",
        "page",
    ]

    def format(self, result: ProcessingResult) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(self.HEADER)
        for tf in result.tagged_fields:
            writer.writerow(
                [
                    result.document_id,
                    result.document_type.value,
                    tf.semantic_tag,
                    tf.normalised_value if tf.normalised_value is not None else tf.value,
                    tf.value,
                    tf.confidence,
                    tf.page or "",
                ]
            )
        return buf.getvalue()
