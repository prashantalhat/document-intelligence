"""Document type registry -- loads ``config/document_types.yaml`` and
provides look-up helpers for classifiers, taggers, and extractors.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any, Type

import yaml
from pydantic import BaseModel

from document_intelligence.models.documents import DocumentType

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "document_types.yaml"


class DocumentTypeConfig:
    """Parsed configuration for a single document type."""

    def __init__(self, key: str, data: dict[str, Any]) -> None:
        self.key = key
        self.display_name: str = data.get("display_name", key)
        self.keywords: list[str] = [str(k).lower() for k in data.get("keywords", [])]
        self.fields: dict[str, list[str]] = {
            tag: [alias.lower() for alias in aliases]
            for tag, aliases in data.get("fields", {}).items()
        }
        self._schema_path: str | None = data.get("schema")

    def get_schema_class(self) -> Type[BaseModel] | None:
        """Dynamically import and return the Pydantic model, or ``None``."""
        if not self._schema_path:
            return None
        module_path, class_name = self._schema_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        return getattr(module, class_name)


class DocumentTypeRegistry:
    """Central registry of all known document types and their configs."""

    def __init__(self, config_path: Path | str | None = None) -> None:
        self._path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
        self._types: dict[str, DocumentTypeConfig] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get(self, doc_type: DocumentType) -> DocumentTypeConfig | None:
        return self._types.get(doc_type.value)

    def all_types(self) -> list[DocumentTypeConfig]:
        return list(self._types.values())

    def keywords_for(self, doc_type: DocumentType) -> list[str]:
        cfg = self.get(doc_type)
        return cfg.keywords if cfg else []

    def field_aliases(self, doc_type: DocumentType) -> dict[str, list[str]]:
        cfg = self.get(doc_type)
        return cfg.fields if cfg else {}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load(self) -> None:
        if not self._path.exists():
            logger.warning("Config file not found: %s", self._path)
            return
        with open(self._path, "r", encoding="utf-8") as fh:
            raw: dict[str, Any] = yaml.safe_load(fh) or {}
        for key, data in raw.items():
            self._types[key] = DocumentTypeConfig(key, data)
        logger.info("Loaded %d document type configs from %s", len(self._types), self._path)
