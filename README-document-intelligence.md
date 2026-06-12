# Document Intelligence

Financial document processing pipeline that ingests PDFs, scanned images, and
digital documents, extracts structured data, applies semantic tags, and outputs
clean JSON or CSV for downstream systems.

## Architecture

```
               +-------------+
  Upload  -->  |   Ingest    |  (file storage, metadata)
               +------+------+
                      |
               +------v------+
               |  Classify   |  (keyword scorer -> document type)
               +------+------+
                      |
               +------v------+
               |   Extract   |  (Docling OCR + layout + tables + schema)
               +------+------+
                      |
               +------v------+
               |     Tag     |  (alias matching -> semantic labels)
               +------+------+
                      |
               +------v------+
               |   Format    |  (JSON / CSV output)
               +-------------+
```

### Design Principles

- **Modular pipeline** -- each stage is a separate class behind an interface.
  Swap Docling for Chandra or Azure DI by implementing `BaseExtractor`.
- **Config-driven document types** -- add new types (invoice, bank statement,
  tax form) by editing `config/document_types.yaml`. No code changes required.
- **Schema-first extraction** -- Pydantic models define the expected fields per
  document type. Docling's structured extraction fills them automatically.
- **Graceful degradation** -- if structured extraction is not available (e.g.
  the `docling[extract]` extra is not installed), the system falls back to
  regex-based key-value extraction from markdown.

## Quick Start

### Prerequisites

- Python 3.10 or higher
- (Optional) GPU for faster OCR / VLM inference

### Install

```bash
# Clone
git clone <repo-url> document-intelligence
cd document-intelligence

# Create virtualenv
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/macOS

# Install with all extras
pip install -e ".[all]"

# Or minimal (Docling only, no structured extraction)
pip install -e .
```

### Configure

```bash
copy .env.example .env
# Edit .env as needed
```

### Run the API server

```bash
di-server --reload
# or: uvicorn document_intelligence.api.app:create_app --factory --reload
```

The API is available at `http://localhost:8000`.
Interactive docs: `http://localhost:8000/docs`.

### Process a document

```bash
# Single file
curl -X POST http://localhost:8000/api/v1/process \
  -F "file=@rental_statement.pdf"

# With explicit type
curl -X POST http://localhost:8000/api/v1/process \
  -F "file=@rental_statement.pdf" \
  -F "document_type=rental_statement"

# CSV output
curl -X POST http://localhost:8000/api/v1/process \
  -F "file=@rental_statement.pdf" \
  -F "output_format=csv"

# Batch
curl -X POST http://localhost:8000/api/v1/process/batch \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.pdf"
```

### Python SDK usage

```python
from document_intelligence.core.pipeline import DocumentPipeline

pipeline = DocumentPipeline()
result = pipeline.process("path/to/rental_statement.pdf")

for field in result.tagged_fields:
    print(f"{field.semantic_tag}: {field.normalised_value} (conf={field.confidence})")
```

## Project Structure

```
document-intelligence/
  config/
    document_types.yaml        # Document type definitions + field aliases
  src/document_intelligence/
    api/
      app.py                   # FastAPI factory + lifespan
      routes.py                # HTTP endpoints
      schemas.py               # Request/response Pydantic models
    classifiers/
      keyword_classifier.py    # Keyword-based doc type detection
    config/
      settings.py              # pydantic-settings configuration
    core/
      pipeline.py              # Main orchestration pipeline
      type_registry.py         # YAML config loader
    extractors/
      base.py                  # Abstract extractor interface
      docling_extractor.py     # IBM Docling extraction engine
    formatters/
      json_formatter.py        # JSON output
      csv_formatter.py         # CSV output
    models/
      documents.py             # Core domain models
      rental.py                # Rental statement Pydantic schema
    taggers/
      field_tagger.py          # Semantic label assignment
    cli.py                     # di-server entry point
  tests/
    unit/                      # Fast tests (no external deps)
    integration/               # API integration tests
  pyproject.toml
  .env.example
```

## API Endpoints

| Method | Path                       | Description                          |
|--------|----------------------------|--------------------------------------|
| GET    | `/api/v1/health`           | Health check                         |
| POST   | `/api/v1/process`          | Process a single document            |
| POST   | `/api/v1/process/batch`    | Process multiple documents           |
| GET    | `/api/v1/document-types`   | List supported types + field maps    |

## Adding a New Document Type

1. Add a section to `config/document_types.yaml` with keywords and field
   aliases.
2. (Optional) Create a Pydantic schema in `src/document_intelligence/models/`
   and reference it in the YAML `schema` field for structured extraction.
3. Add the type to the `DocumentType` enum in `models/documents.py`.

No pipeline code changes needed.

## Extraction Engines

### Docling (default)

IBM's open-source document parser. Handles PDF, DOCX, XLSX, images, and more.
Supports OCR, table extraction, layout analysis, and optional structured
extraction via the NuExtract model.

Install structured extraction: `pip install -e ".[extract]"`

### Chandra OCR (alternative)

Datalab's OCR model with strong table, handwriting, and multilingual support.
Planned as a secondary engine -- implement by subclassing `BaseExtractor`.

Install: `pip install -e ".[chandra]"`

## Testing

```bash
# Unit tests (no Docling / GPU needed)
pytest tests/unit -v

# Integration tests
pytest tests/integration -v

# All tests
pytest -v
```

## Environment Variables

All prefixed with `DI_`. See `.env.example` for the full list.

| Variable                  | Default              | Description                        |
|---------------------------|----------------------|------------------------------------|
| `DI_EXTRACTION_ENGINE`    | `docling`            | `docling` or `chandra`             |
| `DI_UPLOAD_DIR`           | `data/uploads`       | Where uploaded files are stored    |
| `DI_OUTPUT_DIR`           | `data/output`        | Where output files are written     |
| `DI_LOG_LEVEL`            | `INFO`               | Python logging level               |
| `DI_DOCLING_OCR_ENABLED`  | `true`               | Enable OCR for scanned docs        |
| `DI_DOCLING_USE_VLM`      | `false`              | Use Granite-Docling VLM pipeline   |
| `DI_MAX_UPLOAD_SIZE_MB`   | `50`                 | Max file upload size               |
