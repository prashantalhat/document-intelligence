"""API route definitions.

All endpoints live under ``/api/v1`` (prefix applied in ``app.py``).
"""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, PlainTextResponse

from document_intelligence.api.schemas import (
    DocumentTypeParam,
    HealthResponse,
    OutputFormatParam,
    ProcessResponse,
)
from document_intelligence.models.documents import DocumentType, ProcessingStatus

logger = logging.getLogger(__name__)
router = APIRouter()

# Maximum upload size enforced at the application layer (bytes).
_MAX_SIZE = 50 * 1024 * 1024  # 50 MB


# ------------------------------------------------------------------
# Health
# ------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse, tags=["ops"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1.0")


# ------------------------------------------------------------------
# Process a single document
# ------------------------------------------------------------------


@router.post(
    "/process",
    response_model=ProcessResponse,
    tags=["documents"],
    summary="Upload and process a single document",
)
async def process_document(
    request: Request,
    file: Annotated[UploadFile, File(description="The document to process")],
    document_type: Annotated[
        DocumentTypeParam | None,
        Form(description="Optional: skip classification and use this type"),
    ] = None,
    output_format: Annotated[
        OutputFormatParam,
        Form(description="Desired output format"),
    ] = OutputFormatParam.json,
) -> JSONResponse | PlainTextResponse:
    """Accept a file upload, run it through the full pipeline, and return
    structured output.

    Supported file types: PDF, PNG, JPEG, TIFF, DOCX, XLSX.
    """
    settings = request.app.state.settings
    pipeline = request.app.state.pipeline

    # -- validate size --
    if file.size and file.size > _MAX_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit.")

    # -- persist to upload dir --
    upload_id = str(uuid.uuid4())
    suffix = Path(file.filename or "document").suffix
    dest = settings.upload_dir / f"{upload_id}{suffix}"
    try:
        with open(dest, "wb") as fh:
            shutil.copyfileobj(file.file, fh)
    except Exception as exc:
        logger.exception("Failed to save upload")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file.") from exc

    # -- map optional doc type --
    doc_type: DocumentType | None = None
    if document_type is not None:
        try:
            doc_type = DocumentType(document_type.value)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Unknown document type: {document_type}")

    # -- run pipeline --
    try:
        result = pipeline.process(dest, document_type=doc_type)
    except Exception as exc:
        logger.exception("Pipeline processing failed")
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}") from exc

    # -- format output --
    if output_format == OutputFormatParam.csv:
        csv_text = pipeline._csv_formatter.format(result)
        return PlainTextResponse(content=csv_text, media_type="text/csv")

    json_dict = pipeline._json_formatter.format_dict(result)
    return JSONResponse(content=json_dict)


# ------------------------------------------------------------------
# Batch processing endpoint
# ------------------------------------------------------------------


@router.post(
    "/process/batch",
    tags=["documents"],
    summary="Upload and process multiple documents",
)
async def process_batch(
    request: Request,
    files: list[UploadFile] = File(..., description="One or more documents"),
    document_type: Annotated[
        DocumentTypeParam | None,
        Form(description="Optional type override applied to all files"),
    ] = None,
) -> JSONResponse:
    """Process multiple documents in a single request.

    Returns a JSON array of results, one per document. Failures on
    individual documents do not abort the entire batch.
    """
    settings = request.app.state.settings
    pipeline = request.app.state.pipeline

    doc_type: DocumentType | None = None
    if document_type is not None:
        try:
            doc_type = DocumentType(document_type.value)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Unknown document type: {document_type}")

    results = []
    for file in files:
        upload_id = str(uuid.uuid4())
        suffix = Path(file.filename or "document").suffix
        dest = settings.upload_dir / f"{upload_id}{suffix}"
        try:
            with open(dest, "wb") as fh:
                shutil.copyfileobj(file.file, fh)
            result = pipeline.process(dest, document_type=doc_type)
            results.append(pipeline._json_formatter.format_dict(result))
        except Exception as exc:
            logger.exception("Batch item failed: %s", file.filename)
            results.append(
                {
                    "filename": file.filename,
                    "status": ProcessingStatus.FAILED.value,
                    "error": str(exc),
                }
            )

    return JSONResponse(content={"results": results, "total": len(results)})


# ------------------------------------------------------------------
# Supported document types
# ------------------------------------------------------------------


@router.get(
    "/document-types",
    tags=["documents"],
    summary="List supported document types and their field mappings",
)
async def list_document_types(request: Request) -> JSONResponse:
    registry = request.app.state.pipeline._type_registry
    types = []
    for cfg in registry.all_types():
        types.append(
            {
                "key": cfg.key,
                "display_name": cfg.display_name,
                "keywords": cfg.keywords,
                "fields": list(cfg.fields.keys()),
            }
        )
    return JSONResponse(content={"document_types": types})
