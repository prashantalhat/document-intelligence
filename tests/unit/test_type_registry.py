"""Unit tests for the document type registry."""

from document_intelligence.core.type_registry import DocumentTypeRegistry
from document_intelligence.models.documents import DocumentType


class TestDocumentTypeRegistry:
    def test_loads_default_config(self) -> None:
        reg = DocumentTypeRegistry()
        assert len(reg.all_types()) >= 1

    def test_rental_statement_exists(self) -> None:
        reg = DocumentTypeRegistry()
        cfg = reg.get(DocumentType.RENTAL_STATEMENT)
        assert cfg is not None
        assert "rent" in cfg.keywords
        assert "tenant_name" in cfg.fields

    def test_keywords_for_unknown_returns_empty(self) -> None:
        reg = DocumentTypeRegistry()
        kws = reg.keywords_for(DocumentType.UNKNOWN)
        assert kws == []

    def test_field_aliases(self) -> None:
        reg = DocumentTypeRegistry()
        aliases = reg.field_aliases(DocumentType.RENTAL_STATEMENT)
        assert "tenant_name" in aliases
        assert "tenant" in aliases["tenant_name"]
