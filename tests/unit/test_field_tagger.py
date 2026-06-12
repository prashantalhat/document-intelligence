"""Unit tests for the field tagger."""

from document_intelligence.core.type_registry import DocumentTypeRegistry
from document_intelligence.models.documents import (
    DocumentType,
    ExtractedField,
    ExtractionResult,
)
from document_intelligence.taggers.field_tagger import FieldTagger


def _make_extraction(fields: list[ExtractedField]) -> ExtractionResult:
    return ExtractionResult(
        document_id="test-id",
        document_type=DocumentType.RENTAL_STATEMENT,
        fields=fields,
    )


class TestFieldTagger:
    def setup_method(self) -> None:
        self.registry = DocumentTypeRegistry()
        self.tagger = FieldTagger(self.registry)

    def test_exact_match(self) -> None:
        ext = _make_extraction([ExtractedField(key="tenant name", value="Jane Doe", confidence=0.9)])
        tagged = self.tagger.tag(ext)
        assert len(tagged) == 1
        assert tagged[0].semantic_tag == "tenant_name"
        assert tagged[0].confidence == 0.9  # 0.9 * 1.0

    def test_substring_match(self) -> None:
        ext = _make_extraction([ExtractedField(key="Monthly Rent Amount", value="$1,500", confidence=0.8)])
        tagged = self.tagger.tag(ext)
        assert len(tagged) == 1
        assert tagged[0].semantic_tag == "rent_amount"

    def test_value_normalisation_currency(self) -> None:
        ext = _make_extraction([ExtractedField(key="balance due", value="$2,350.00", confidence=0.85)])
        tagged = self.tagger.tag(ext)
        assert tagged[0].normalised_value == 2350.00

    def test_unmatched_field_passes_through(self) -> None:
        ext = _make_extraction([ExtractedField(key="foobarbaz", value="x", confidence=0.7)])
        tagged = self.tagger.tag(ext)
        assert len(tagged) == 1
        assert tagged[0].semantic_tag == "foobarbaz"
        assert tagged[0].confidence < 0.7  # reduced for low-match
