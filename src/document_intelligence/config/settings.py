"""Application settings loaded from environment / .env file.

Uses pydantic-settings so every value can be overridden via env vars
prefixed with ``DI_`` (e.g. ``DI_UPLOAD_DIR=/data/uploads``).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the document-intelligence service."""

    model_config = SettingsConfigDict(
        env_prefix="DI_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # -- general --
    app_name: str = "document-intelligence"
    debug: bool = False
    log_level: str = "INFO"

    # -- file storage --
    upload_dir: Path = Path("data/uploads")
    output_dir: Path = Path("data/output")
    max_upload_size_mb: int = 50

    # -- extraction engine --
    extraction_engine: Literal["docling", "chandra"] = "docling"

    # -- docling-specific --
    docling_ocr_enabled: bool = True
    docling_use_vlm: bool = False
    docling_vlm_model: str = "granite_docling"

    # -- chandra-specific --
    chandra_method: Literal["vllm", "hf"] = "vllm"
    chandra_vllm_api_base: str = "http://localhost:8000/v1"

    # -- API --
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1

    # -- limits --
    max_concurrent_jobs: int = 4


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton ``Settings`` instance."""
    return Settings()
