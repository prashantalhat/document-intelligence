"""Unit tests for output formatters."""

import json

from document_intelligence.formatters.csv_formatter import CsvFormatter
from document_intelligence.formatters.json_formatter import JsonFormatter
from document_intelligence.models.documents import (
    DocumentMetadata,
    DocumentType,
    ProcessingResult,
    ProcessingStatus,
    TaggedField,
)


def _make_result() -> ProcessingResult:
    meta = DocumentMetadata(filename="test.pdf", file_path="/test.pdf")
    return ProcessingResult(
        document_id=meta.document_id,
        metadata=meta,
        document_type=DocumentType.RENTAL_STATEMENT,
        status=ProcessingStatus.COMPLETED,
        tagged_fields=[
            TaggedField(
                semantic_tag="tenant_name",
                raw_key="Tenant Name",
                value="Jane Doe",
                normalised_value="Jane Doe",
                confidence=0.9,
                page=1,
            ),
            TaggedField(
                semantic_tag="rent_amount",
                raw_key="Rent",
                value="$1,500.00",
                normalised_value=1500.0,
                confidence=0.85,
                page=1,
            ),
        ],
    )


class TestJsonFormatter:
    def test_output_is_valid_json(self) -> None:
        fmt = JsonFormatter()
        text = fmt.format(_make_result())
        data = json.loads(text)
        assert data["document_type"] == "rental_statement"
        assert "tenant_name" in data["fields"]

    def test_format_dict(self) -> None:
        fmt = JsonFormatter()
        d = fmt.format_dict(_make_result())
        assert isinstance(d, dict)
        assert d["fields"]["rent_amount"]["value"] == 1500.0


class TestCsvFormatter:
    def test_header_row(self) -> None:
        fmt = CsvFormatter()
        csv_text = fmt.format(_make_result())
        lines = csv_text.strip().split("\n")
        assert lines[0].startswith("document_id,")
        assert len(lines) == 3  # header + 2 data rows

    def test_field_values(self) -> None:
        fmt = CsvFormatter()
        csv_text = fmt.format(_make_result())
        assert "tenant_name" in csv_text
        assert "1500.0" in csv_text
