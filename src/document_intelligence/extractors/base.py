"""Abstract base class for extraction engines.

Every extraction back-end (Docling, Chandra, Azure DI, ...) must implement
this interface so the pipeline can swap engines without changing orchestration
logic.
"""

from __future__ import annotations

import abc
from pathlib import Path

from document_intelligence.models.documents import DocumentType, ExtractionResult


class BaseExtractor(abc.ABC):
    """Contract that all extraction engines must satisfy."""

    @abc.abstractmethod
    def extract(self, file_path: Path, document_type: DocumentType) -> ExtractionResult:
        """Extract structured data from a document.

        Parameters
        ----------
        file_path:
            Absolute path to the file on disk.
        document_type:
            The classified type, used to select the correct extraction
            schema / template.

        Returns
        -------
        ExtractionResult
        """

    @abc.abstractmethod
    def supports_format(self, mime_type: str) -> bool:
        """Return ``True`` if this engine can handle the given MIME type."""
