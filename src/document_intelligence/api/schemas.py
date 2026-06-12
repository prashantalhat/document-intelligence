"""Pydantic models for API request / response serialisation."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DocumentTypeParam(str, Enum):
    """Accepted document_type form values."""

    rental_statement = "rental_statement"
    invoice = "invoice"
    bank_statement = "bank_statement"
    tax_form = "tax_form"


class OutputFormatParam(str, Enum):
    """Accepted output_format form values."""

    json = "json"
    csv = "csv"


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"


class FieldOutput(BaseModel):
    value: Any
    raw_value: Any
    confidence: float
    page: int | None = None


class ProcessResponse(BaseModel):
    document_id: str
    document_type: str
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    fields: dict[str, FieldOutput] = Field(default_factory=dict)
    tables: list[list[list[str]]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    processing_duration_ms: float = 0.0
    processed_at: str = ""
