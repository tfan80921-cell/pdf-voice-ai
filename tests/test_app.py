"""
Tests for PDF Voice AI application.
"""
import json
from pathlib import Path

import pytest

from app.config import settings
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    RackCreate,
    RackResponse,
    NotebookCreate,
    NotebookResponse,
    UploadResponse,
    HealthResponse,
    ErrorResponse,
    AIProvider,
)
from app.db import is_neon_enabled


class TestConfig:
    """Test configuration values."""

    def test_settings_has_required_fields(self):
        """Verify config has all required fields."""
        assert settings.APP_NAME == "PDF Voice AI"
        assert settings.APP_VERSION == "1.0.0"
        assert settings.DEBUG in (True, False)
        assert settings.HOST
        assert settings.PORT > 0
        assert settings.UPLOAD_DIR.exists() or settings.UPLOAD_DIR.mkdir(
            parents=True, exist_ok=True
        )

    def test_allowed_origins(self):
        """Verify CORS origins are configured."""
        assert settings.ALLOWED_ORIGINS is not None
        assert len(settings.ALLOWED_ORIGINS) > 0


class TestSchemas:
    """Test pydantic schema validation."""

    def test_rack_create_valid(self):
        """RackCreate should validate successfully."""
        body = RackCreate(name="Test Project", description="Test description")
        assert body.name == "Test Project"
        assert body.description == "Test description"

    def test_rack_create_min_name(self):
        """RackCreate should reject empty name."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RackCreate(name="", description="")

    def test_chat_request_valid(self):
        """ChatRequest should validate with minimal data."""
        body = ChatRequest(
            query="test query",
            rack_id="rack-1",
            provider=AIProvider.GEMINI,
            api_key="valid-key-1234567890",
        )
        assert body.query == "test query"
        assert body.rack_id == "rack-1"

    def test_chat_request_strips_query(self):
        """ChatRequest should strip query whitespace."""
        body = ChatRequest(
            query="  hello  ",
            rack_id="rack-1",
            provider=AIProvider.GEMINI,
            api_key="valid-key-1234567890",
        )
        assert body.query == "hello"

    def test_health_response(self):
        """HealthResponse should have required fields."""
        body = HealthResponse(
            status="ok",
            version="1.0.0",
            racks=0,
            documents_indexed=0,
            providers=["gemini"],
        )
        assert body.status == "ok"
        assert body.racks == 0


class TestDb:
    """Test database utilities."""

    def test_is_neon_enabled_false(self):
        """is_neon_enabled returns False when DATABASE_URL is empty."""
        from app.config import settings as s

        # settings is a module-level singleton: restore it, otherwise an empty
        # value leaks into every later test and init_db() never creates the engine.
        original = s.DATABASE_URL
        try:
            s.DATABASE_URL = ""
            assert is_neon_enabled() is False
        finally:
            s.DATABASE_URL = original

    def test_is_neon_enabled_true(self):
        """is_neon_enabled returns True when DATABASE_URL is set."""
        from app.config import settings as s

        # settings is a module-level singleton: restore it, otherwise this
        # value leaks into every later test in the session.
        original = s.DATABASE_URL
        try:
            s.DATABASE_URL = "postgresql://user:pass@host/db"
            assert is_neon_enabled() is True
        finally:
            s.DATABASE_URL = original


class TestEndpoints:
    """Test FastAPI endpoint behavior (client integration tests)."""

    @pytest.fixture(autouse=True)
    def setup_app(self, client):
        """Set up test client from the lifespan-aware shared fixture."""
        self.client = client

    def test_health_endpoint(self):
        """GET /api/health returns health response."""
        response = self.client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "racks" in data
        assert "providers" in data

    def test_list_racks_empty(self):
        """GET /api/racks returns empty list when no projects."""
        response = self.client.get("/api/racks")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_rack(self):
        """POST /api/racks creates a new project."""
        response = self.client.post(
            "/api/racks",
            json={"name": "Test Project", "description": "Desc"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Project"
        assert "id" in data

    def test_create_rack_duplicate_id(self):
        """POST /api/racks should generate unique ID on collision."""
        # Create first rack
        self.client.post("/api/racks", json={"name": "Project A"})
        # Create second rack with same slugified ID
        response = self.client.post(
            "/api/racks", json={"name": "Project A"}
        )
        assert response.status_code == 201
        # Should have different ID
        assert response.json()["id"] != "project-a"

    def test_upload_no_file(self):
        """POST /api/racks/{id}/upload should reject missing file."""
        response = self.client.post(
            "/api/racks",
            json={"name": "Proyecto de prueba", "description": "Prueba"},
        )
        rack_id = response.json()["id"]
        try:
            notebook = self.client.post(
                f"/api/racks/{rack_id}/notebooks",
                json={"name": "Cuaderno de prueba"},
            ).json()
            # Upload without file: the route requires a notebook, and a missing
            # multipart field is a 422 validation error, not a 400.
            response = self.client.post(
                f"/api/racks/{rack_id}/notebooks/{notebook['id']}/upload",
                files={},
            )
            assert response.status_code == 422
        finally:
            self.client.delete(f"/api/racks/{rack_id}")

    def test_chat_no_documents(self):
        """POST /api/chat should reject when no documents indexed."""
        response = self.client.post(
            "/api/chat",
            json={
                "query": "test",
                "rack_id": "non-existent",
                "provider": "gemini",
                "api_key": "valid-key-1234567890",
            },
        )
        assert response.status_code == 404