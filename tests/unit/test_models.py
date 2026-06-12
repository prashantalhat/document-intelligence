"""Unit tests for domain models."""

from document_intelligence.models.documents import (
    DocumentMetadata,
    DocumentType,
    ExtractedField,
    ExtractionResult,
    ProcessingResult,
    ProcessingStatus,
    TaggedField,
)
from document_intelligence.models.rental import RentalLineItem, RentalStatement


class TestDocumentType:
    def test_enum_values(self) -> None:
        assert DocumentType.RENTAL_STATEMENT.value == "rental_statement"
        assert DocumentType.INVOICE.value == "invoice"
        assert DocumentType.UNKNOWN.value == "unknown"


class TestDocumentMetadata:
    def test_default_id_generated(self) -> None:
        m = DocumentMetadata(filename="test.pdf", file_path="/tmp/test.pdf")
        assert m.document_id  # non-empty UUID string
        assert m.mime_type == "application/octet-stream"

    def test_custom_fields(self) -> None:
        m = DocumentMetadata(
            filename="rent.pdf",
            file_path="/data/rent.pdf",
            file_size_bytes=12345,
            mime_type="application/pdf",
        )
        assert m.file_size_bytes == 12345
        assert m.mime_type == "application/pdf"


class TestExtractedField:
    def test_confidence_bounds(self) -> None:
        f = ExtractedField(key="amount", value="100", confidence=0.95)
        assert 0.0 <= f.confidence <= 1.0

    def test_optional_bbox(self) -> None:
        f = ExtractedField(key="name", value="Jane")
        assert f.bounding_box is None


class TestRentalStatement:
    def test_default_values(self) -> None:
        rs = RentalStatement()
        assert rs.tenant_name is None
        assert rs.line_items == []

    def test_full_model(self) -> None:
        rs = RentalStatement(
            tenant_name="Jane Doe",
            landlord_name="Acme Props",
            rent_amount=1500.00,
            balance_due=150.00,
            line_items=[
                RentalLineItem(description="Rent", amount=1500.00),
                RentalLineItem(description="Late Fee", amount=50.00),
            ],
        )
        assert rs.tenant_name == "Jane Doe"
        assert len(rs.line_items) == 2
        assert rs.line_items[1].amount == 50.00


class TestProcessingResult:
    def test_completed_status(self) -> None:
        meta = DocumentMetadata(filename="x.pdf", file_path="/x.pdf")
        r = ProcessingResult(
            document_id=meta.document_id,
            metadata=meta,
            document_type=DocumentType.RENTAL_STATEMENT,
            status=ProcessingStatus.COMPLETED,
        )
        assert r.status == ProcessingStatus.COMPLETED
        assert r.errors == []
