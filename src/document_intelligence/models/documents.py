"""Core domain models for the document processing pipeline.

These models define the data structures that flow through every stage of the
pipeline: ingestion -> classification -> extraction -> tagging -> output.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DocumentType(str, Enum):
    """Known document types the system can classify and extract."""

    RENTAL_STATEMENT = "rental_statement"
    INVOICE = "invoice"
    BANK_STATEMENT = "bank_statement"
    TAX_FORM = "tax_form"
    PAY_STUB = "pay_stub"
    RECEIPT = "receipt"
    UTILITY_BILL = "utility_bill"
    INSURANCE_DOCUMENT = "insurance_document"
    UNKNOWN = "unknown"


class ProcessingStatus(str, Enum):
    """Lifecycle status of a document going through the pipeline."""

    PENDING = "pending"
    CLASSIFYING = "classifying"
    EXTRACTING = "extracting"
    TAGGING = "tagging"
    FORMATTING = "formatting"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

class ClassificationResult(BaseModel):
    """Output of the classification stage with confidence scores."""

    document_type: DocumentType
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    scores: dict[str, float] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

class DocumentMetadata(BaseModel):
    """Metadata collected at ingestion time."""

    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    file_path: str
    file_size_bytes: int = 0
    mime_type: str = "application/octet-stream"
    page_count: int = 0
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = "upload"  # upload | batch | api


class ExtractedField(BaseModel):
    """A single key-value pair pulled from a document by an extractor."""

    key: str
    value: Any
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    page: int | None = None
    bounding_box: list[float] | None = None  # [x0, y0, x1, y1] normalised


class TaggedField(BaseModel):
    """An extracted field enriched with a semantic label."""

    semantic_tag: str  # e.g. "rent_amount", "tenant_name"
    raw_key: str
    value: Any
    normalised_value: Any | None = None  # cleaned / cast value
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    page: int | None = None


# ---------------------------------------------------------------------------
# Pipeline stage results
# ---------------------------------------------------------------------------

class ExtractionResult(BaseModel):
    """Output of the extraction stage."""

    document_id: str
    document_type: DocumentType
    fields: list[ExtractedField] = Field(default_factory=list)
    tables: list[list[list[str]]] = Field(default_factory=list)  # list of 2-D tables
    raw_text: str = ""
    raw_markdown: str = ""
    extraction_engine: str = "docling"
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProcessingResult(BaseModel):
    """Final output after the full pipeline has run."""

    document_id: str
    metadata: DocumentMetadata
    document_type: DocumentType
    status: ProcessingStatus
    tagged_fields: list[TaggedField] = Field(default_factory=list)
    tables: list[list[list[str]]] = Field(default_factory=list)
    raw_text: str = ""
    raw_markdown: str = ""
    errors: list[str] = Field(default_factory=list)
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    processing_duration_ms: float = 0.0
