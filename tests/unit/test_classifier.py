"""Unit tests for the keyword classifier.

These tests avoid calling Docling by creating text files (which the
classifier reads directly).
"""

import tempfile
from pathlib import Path

from document_intelligence.classifiers.keyword_classifier import KeywordClassifier
from document_intelligence.core.type_registry import DocumentTypeRegistry
from document_intelligence.models.documents import DocumentType


class TestKeywordClassifier:
    def setup_method(self) -> None:
        self.registry = DocumentTypeRegistry()
        self.classifier = KeywordClassifier(self.registry)

    def test_filename_match(self, tmp_path: Path) -> None:
        f = tmp_path / "rental_statement.txt"
        f.write_text("some content", encoding="utf-8")
        assert self.classifier.classify(f) == DocumentType.RENTAL_STATEMENT

    def test_content_match_rental(self, tmp_path: Path) -> None:
        f = tmp_path / "document.txt"
        f.write_text(
            "Statement for Tenant: Jane Doe\n"
            "Property: 123 Main St\n"
            "Monthly Rent: $1,500.00\n"
            "Balance Due: $150.00\n"
            "Landlord: Acme Properties\n",
            encoding="utf-8",
        )
        assert self.classifier.classify(f) == DocumentType.RENTAL_STATEMENT

    def test_content_match_invoice(self, tmp_path: Path) -> None:
        f = tmp_path / "document.txt"
        f.write_text(
            "Invoice Number: INV-2025-001\n"
            "Subtotal: $500.00\n"
            "Tax: $50.00\n"
            "Total: $550.00\n"
            "Payment due within 30 days\n"
            "Purchase Order: PO-123\n",
            encoding="utf-8",
        )
        assert self.classifier.classify(f) == DocumentType.INVOICE

    def test_unknown_document(self, tmp_path: Path) -> None:
        f = tmp_path / "random.txt"
        f.write_text("Hello world, nothing special here.", encoding="utf-8")
        assert self.classifier.classify(f) == DocumentType.UNKNOWN
