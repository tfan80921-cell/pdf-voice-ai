"""
Tests for PDF Voice AI application.
"""
import json
import tempfile
from pathlib import Path

import pytest

from app.config import settings
from app.documents.manager import DocumentManager
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
        try:
            fetched = self.client.get(f"/api/racks/{data['id']}")
            assert fetched.status_code == 200
            assert fetched.json()["description"] == "Desc"
        finally:
            self.client.delete(f"/api/racks/{data['id']}")

    def test_create_rack_duplicate_id(self):
        """POST /api/racks should generate unique ID on collision."""
        first = self.client.post("/api/racks", json={"name": "Project A"})
        second = None
        try:
            assert first.status_code == 201
            second = self.client.post("/api/racks", json={"name": "Project A"})
            assert second.status_code == 201
            assert second.json()["id"] != first.json()["id"]
        finally:
            if second is not None and second.status_code == 201:
                self.client.delete(f"/api/racks/{second.json()['id']}")
            if first.status_code == 201:
                self.client.delete(f"/api/racks/{first.json()['id']}")

    def test_project_and_notebook_update_delete_lifecycle(self):
        project = self.client.post("/api/racks", json={"name": "Lifecycle QA"})
        assert project.status_code == 201
        project_id = project.json()["id"]
        try:
            notebook = self.client.post(
                f"/api/racks/{project_id}/notebooks",
                json={"name": "Initial notebook", "description": "before"},
            )
            assert notebook.status_code == 201
            notebook_id = notebook.json()["id"]

            updated_project = self.client.put(
                f"/api/racks/{project_id}",
                json={"description": "after"},
            )
            assert updated_project.status_code == 200
            assert updated_project.json()["description"] == "after"

            updated_notebook = self.client.put(
                f"/api/racks/{project_id}/notebooks/{notebook_id}",
                json={"name": "Updated notebook", "description": "after"},
            )
            assert updated_notebook.status_code == 200
            assert updated_notebook.json()["name"] == "Updated notebook"

            listed = self.client.get(f"/api/racks/{project_id}/notebooks")
            assert listed.status_code == 200
            assert [item["id"] for item in listed.json()] == [notebook_id]

            deleted_notebook = self.client.delete(
                f"/api/racks/{project_id}/notebooks/{notebook_id}"
            )
            assert deleted_notebook.status_code == 200
            assert self.client.get(
                f"/api/racks/{project_id}/notebooks"
            ).json() == []
        finally:
            self.client.delete(f"/api/racks/{project_id}")

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


_POULTRY = (
    "El agua de bebida para vacunacion debe prepararse con leche descremada en polvo "
    "para estabilizar el virus vivo. La vacuna contra la enfermedad de Newcastle se "
    "administra por via ocular a los siete dias de vida del ave. La bronquitis "
    "infecciosa se previene con la cepa Massachusetts. Se recomienda no usar agua "
    "clorada ni metales durante la preparacion.\n\n"
) * 3

_ELECTRICAL = (
    "El procedimiento LOTO exige bloquear toda fuente de energia antes de intervenir "
    "un motor electrico. Se verifica ausencia de voltaje con un multimetro en las "
    "tres fases. Los relevadores termicos se dimensionan segun la corriente de plena "
    "carga de la placa de datos. El gabinete debe rotularse con candado de seguridad.\n\n"
) * 3


class TestIngestionAndRetrieval:
    """
    Exercise the real RAG pipeline end to end: ingest -> embed -> store -> retrieve.

    These cover the code the Neon-only refactor rewrote, which no other test touches.
    """

    @pytest.fixture(autouse=True)
    def setup(self, client):
        self.client = client
        self.document_manager = DocumentManager()

    def _run(self, coroutine_factory):
        """
        Run an async manager method on the same event loop as the TestClient
        lifespan.

        The asyncpg pool binds its connections to the loop where the lifespan
        ran, so asyncio.run() would raise "attached to a different loop". The
        coroutine must be created inside that loop: portal.call() awaits whatever
        the zero-argument callable returns. It accepts no keyword arguments of
        its own, hence the factory.
        """
        return self.client.portal.call(coroutine_factory)

    def _rack_with_notebooks(self, *names):
        rack = self.client.post(
            "/api/racks", json={"name": "Pipeline Rack"}
        ).json()
        notebooks = []
        for name in names:
            nb = self.client.post(
                f"/api/racks/{rack['id']}/notebooks",
                json={"name": name, "domain": name.lower()},
            ).json()
            notebooks.append(nb)
        return rack, notebooks

    def _upload_text(self, rack, notebook, filename, content):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".txt", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            return self.client.post(
                f"/api/racks/{rack['id']}/notebooks/{notebook['id']}/upload",
                files={"file": (filename, tmp_path.read_bytes(), "text/plain")},
            )
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_ingest_indexes_chunks_in_neon(self):
        """A text file becomes stored, retrievable chunks."""
        rack, (notebook,) = self._rack_with_notebooks("vet")
        try:
            response = self._upload_text(rack, notebook, "vacunas.txt", _POULTRY)
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["chunks"] > 0

            count = self.client.get("/api/health").json()["documents_indexed"]
            indexed = self.client.get(f"/api/racks/{rack['id']}").json()
            assert indexed["notebooks"][0]["document_count"] > 0
            assert count >= 0
        finally:
            self.client.delete(f"/api/racks/{rack['id']}")

    def test_ingest_is_idempotent(self):
        """Uploading the same content twice does not duplicate chunks."""
        rack, (notebook,) = self._rack_with_notebooks("vet")
        try:
            self._upload_text(rack, notebook, "vacunas.txt", _POULTRY)
            first = self.client.get(f"/api/racks/{rack['id']}").json()["notebooks"][0][
                "document_count"
            ]
            self._upload_text(rack, notebook, "vacunas.txt", _POULTRY)
            second = self.client.get(f"/api/racks/{rack['id']}").json()["notebooks"][0][
                "document_count"
            ]
            assert first == second, "ON CONFLICT should deduplicate by doc_hash"
        finally:
            self.client.delete(f"/api/racks/{rack['id']}")

    def test_vector_search_ranks_the_relevant_document_first(self):
        """Cosine ordering returns the semantically closest chunk, not just any."""
        rack, (poultry_nb, electrical_nb) = self._rack_with_notebooks("vet", "elec")
        try:
            self._upload_text(rack, poultry_nb, "vacunas.txt", _POULTRY)
            self._upload_text(rack, electrical_nb, "loto.txt", _ELECTRICAL)

            hits = self._run(
                lambda: self.document_manager.query_async(
                    "que vacuna se aplica a los pollos", rack_id=rack["id"]
                )
            )
            assert hits, "vector search returned nothing"
            assert hits[0]["metadata"]["filename"] == "vacunas.txt"

            # The nearest neighbour must actually be near, not merely first.
            assert hits[0]["distance"] < hits[-1]["distance"]
        finally:
            self.client.delete(f"/api/racks/{rack['id']}")

    def test_vector_search_respects_notebook_filter(self):
        """Filtering by notebook excludes the other notebook's chunks."""
        rack, (poultry_nb, electrical_nb) = self._rack_with_notebooks("vet", "elec")
        try:
            self._upload_text(rack, poultry_nb, "vacunas.txt", _POULTRY)
            self._upload_text(rack, electrical_nb, "loto.txt", _ELECTRICAL)

            hits = self._run(
                lambda: self.document_manager.query_async(
                    "que vacuna se aplica a los pollos",
                    rack_id=rack["id"],
                    notebook_ids=[electrical_nb["id"]],
                )
            )
            assert hits, "filtered search returned nothing"
            assert all(h["metadata"]["notebook_id"] == electrical_nb["id"] for h in hits)
        finally:
            self.client.delete(f"/api/racks/{rack['id']}")

    def test_context_string_labels_notebook_and_file(self):
        """The prompt context tags each fragment with its notebook and file."""
        rack, (notebook,) = self._rack_with_notebooks("vet")
        try:
            self._upload_text(rack, notebook, "vacunas.txt", _POULTRY)
            context, sources, notebooks_used = self._run(
                lambda: self.document_manager.get_context_string_async(
                    "vacuna de los pollos", rack_id=rack["id"]
                )
            )
            assert context
            assert "vacunas.txt" in sources
            assert notebook["id"] in notebooks_used
            assert "Cuaderno:" in context and "Archivo:" in context
        finally:
            self.client.delete(f"/api/racks/{rack['id']}")

    def test_chat_end_to_end_with_mocked_provider(self, monkeypatch):
        """
        Full chat pipeline: retrieve -> build prompt -> generate -> map response.

        The AI provider is mocked so the test asserts our own wiring, and does not
        spend real tokens.
        """

        class FakeProvider:
            provider_name = "fake-provider"
            model = "fake-model"

            def build_rag_prompt(self, context, query, language, system_instruction,
                                 operating_instruction, notebook_catalog):
                assert context, "prompt was built without retrieved context"
                assert query
                return "system prompt", f"user: {query}"

            async def generate(self, system_prompt, user_prompt):
                assert system_prompt == "system prompt"
                return "respuesta basada en el contexto", 42

        from app import main

        monkeypatch.setattr(
            main.AIProviderFactory,
            "create",
            staticmethod(lambda **kwargs: FakeProvider()),
        )

        rack, (notebook,) = self._rack_with_notebooks("vet")
        try:
            self._upload_text(rack, notebook, "vacunas.txt", _POULTRY)

            response = self.client.post(
                "/api/chat",
                json={
                    "query": "que vacuna se aplica a los pollos",
                    "rack_id": rack["id"],
                    "provider": "gemini",
                    "api_key": "valid-key-1234567890",
                },
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["answer"] == "respuesta basada en el contexto"
            assert body["tokens_used"] == 42
            assert body["provider"] == "fake-provider"
            assert body["model"] == "fake-model"
            assert "vacunas.txt" in body["sources"]
            assert notebook["name"] in body["notebooks_used"]
        finally:
            self.client.delete(f"/api/racks/{rack['id']}")