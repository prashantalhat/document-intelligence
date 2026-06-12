"""Integration tests for the FastAPI application.

These test the HTTP layer (routing, validation, response format) using
httpx's ASGITransport, which does not require a running server.

Docling is not exercised here -- the pipeline will be tested with real
documents in a separate integration suite.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from document_intelligence.api.app import create_app


@pytest.fixture
async def client():
    """Create an async test client with proper lifespan management."""
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
    ) as ac:
        # Manually trigger the lifespan so app.state is populated.
        # FastAPI's TestClient handles this, but httpx's ASGITransport
        # does not. We trigger it by sending the ASGI lifespan events.
        scope = {"type": "lifespan", "asgi": {"version": "3.0"}}

        async def receive():
            return {"type": "lifespan.startup"}

        startup_complete = False

        async def send(message):
            nonlocal startup_complete
            if message["type"] == "lifespan.startup.complete":
                startup_complete = True

        await app(scope, receive, send)
        assert startup_complete, "App lifespan startup did not complete"
        yield ac


class TestHealthEndpoint:
    async def test_health_returns_ok(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestDocumentTypesEndpoint:
    async def test_lists_types(self, client: AsyncClient) -> None:
        resp = await client.get("/api/v1/document-types")
        assert resp.status_code == 200
        data = resp.json()
        assert "document_types" in data
        keys = [t["key"] for t in data["document_types"]]
        assert "rental_statement" in keys


class TestClassifyEndpoint:
    async def test_classify_rental(self, client: AsyncClient) -> None:
        content = (
            b"Tenant Name: Jane Doe\n"
            b"Landlord: Acme Properties\n"
            b"Monthly Rent: $1,500\n"
            b"Lease term: 12 months\n"
        )
        resp = await client.post(
            "/api/v1/classify",
            files={"file": ("statement.txt", content, "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_type"] == "rental_statement"
        assert data["confidence"] > 0
        assert "scores" in data
        assert "rental_statement" in data["scores"]

    async def test_classify_invoice(self, client: AsyncClient) -> None:
        content = (
            b"Invoice Number: INV-2026-001\n"
            b"Subtotal: $500\n"
            b"Tax: $50\n"
            b"Total: $550\n"
            b"Payment due: 2026-07-01\n"
        )
        resp = await client.post(
            "/api/v1/classify",
            files={"file": ("doc.txt", content, "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_type"] == "invoice"

    async def test_classify_unknown(self, client: AsyncClient) -> None:
        content = b"Hello world, this is random text with no financial keywords."
        resp = await client.post(
            "/api/v1/classify",
            files={"file": ("random.txt", content, "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["document_type"] == "unknown"
        assert data["confidence"] == 0.0

    async def test_classify_rejects_missing_file(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/classify")
        assert resp.status_code == 422


class TestProcessEndpoint:
    async def test_rejects_missing_file(self, client: AsyncClient) -> None:
        resp = await client.post("/api/v1/process")
        assert resp.status_code == 422  # validation error -- no file

    async def test_accepts_text_file(self, client: AsyncClient) -> None:
        """Upload a simple .txt file to verify the API plumbing.

        The classifier can read .txt directly, so this avoids
        depending on Docling for a unit-level integration test.
        """
        content = (
            b"Tenant Name: Jane Doe\n"
            b"Property: 123 Main St\n"
            b"Rent: $1,500\n"
            b"Balance Due: $150\n"
        )
        resp = await client.post(
            "/api/v1/process",
            files={"file": ("rental.txt", content, "text/plain")},
            data={"document_type": "rental_statement"},
        )
        # The extractor will fail on .txt (Docling doesn't support plain text
        # in the same way), but the API should still return a response with
        # status=failed rather than crashing.
        assert resp.status_code == 200
        data = resp.json()
        assert "document_id" in data
