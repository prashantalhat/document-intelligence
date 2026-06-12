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

    def test_classify_with_confidence_returns_scores(self, tmp_path: Path) -> None:
        f = tmp_path / "document.txt"
        f.write_text(
            "Tenant: Jane Doe\nRent: $1,500\nLandlord: Acme\nLease: 12 months\n",
            encoding="utf-8",
        )
        result = self.classifier.classify_with_confidence(f)
        assert result.document_type == DocumentType.RENTAL_STATEMENT
        assert result.confidence > 0
        assert "rental_statement" in result.scores
        assert result.scores["rental_statement"] > 0

    def test_classify_with_confidence_unknown_has_zero(self, tmp_path: Path) -> None:
        f = tmp_path / "random.txt"
        f.write_text("Nothing relevant here at all.", encoding="utf-8")
        result = self.classifier.classify_with_confidence(f)
        assert result.document_type == DocumentType.UNKNOWN
        assert result.confidence == 0.0

    def test_filename_match_returns_high_confidence(self, tmp_path: Path) -> None:
        f = tmp_path / "bank_statement.txt"
        f.write_text("some content", encoding="utf-8")
        result = self.classifier.classify_with_confidence(f)
        assert result.document_type == DocumentType.BANK_STATEMENT
        assert result.confidence == 0.9

    def test_content_match_pay_stub(self, tmp_path: Path) -> None:
        f = tmp_path / "document.txt"
        f.write_text(
            "Pay Stub\nEmployee: John Smith\nGross Pay: $5,000\n"
            "Deductions: $800\nNet Pay: $4,200\nPay Period: June 2026\n",
            encoding="utf-8",
        )
        assert self.classifier.classify(f) == DocumentType.PAY_STUB

    def test_content_match_receipt(self, tmp_path: Path) -> None:
        f = tmp_path / "document.txt"
        f.write_text(
            "Receipt\nStore: Corner Shop\nItems purchased: 3\n"
            "Subtotal: $25.00\nTotal: $27.50\nCard ending: 4242\n",
            encoding="utf-8",
        )
        assert self.classifier.classify(f) == DocumentType.RECEIPT

    def test_content_match_utility_bill(self, tmp_path: Path) -> None:
        f = tmp_path / "document.txt"
        f.write_text(
            "Utility Bill\nElectricity usage: 450 kWh\n"
            "Billing period: May 2026\nService address: 10 Oak Ave\n"
            "Amount due: $120.00\nMeter reading: 54321\n",
            encoding="utf-8",
        )
        assert self.classifier.classify(f) == DocumentType.UTILITY_BILL

    def test_content_match_insurance(self, tmp_path: Path) -> None:
        f = tmp_path / "document.txt"
        f.write_text(
            "Certificate of Insurance\nPolicyholder: Jane Doe\n"
            "Policy number: POL-999\nPremium: $2,400\n"
            "Coverage: $500,000\nDeductible: $1,000\n",
            encoding="utf-8",
        )
        assert self.classifier.classify(f) == DocumentType.INSURANCE_DOCUMENT
