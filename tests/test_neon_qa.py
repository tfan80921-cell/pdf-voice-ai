"""Focused Neon configuration, PDF, and opt-in end-to-end QA tests."""
from __future__ import annotations

import asyncio
import importlib
import math
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db import _register_vector_codec, _to_async_url
from app.documents.manager import DocumentManager
from tests.pdf_factory import make_test_pdf


@pytest.mark.parametrize(
    ("url", "expected_scheme", "expected_query"),
    [
        (
            "postgres://qa:password@db.example/qa?sslmode=require&channel_binding=require",
            "postgresql+asyncpg",
            {"ssl": "require"},
        ),
        (
            "postgresql://qa:password@db.example/qa?sslmode=verify-full&application_name=qa",
            "postgresql+asyncpg",
            {"ssl": "verify-full", "application_name": "qa"},
        ),
        (
            "postgresql+asyncpg://qa:password@db.example/qa?sslmode=require",
            "postgresql+asyncpg",
            {"ssl": "require"},
        ),
    ],
)
def test_async_url_normalizes_neon_parameters(url, expected_scheme, expected_query):
    from urllib.parse import parse_qsl, urlsplit

    normalized = _to_async_url(url)
    parts = urlsplit(normalized)
    assert parts.scheme == expected_scheme
    assert dict(parse_qsl(parts.query)) == expected_query
    assert "channel_binding" not in parts.query


def test_pdf_fixture_extracts_text_and_reports_page_count(tmp_path):
    pdf_path = tmp_path / "qa-document.pdf"
    pdf_path.write_bytes(make_test_pdf("QA-EXTRACT marker 7831"))

    manager = object.__new__(DocumentManager)
    extracted, page_count = manager._extract_pdf(pdf_path)

    assert page_count == 1
    assert "QA-EXTRACT marker 7831" in extracted


def test_pdf_page_limit_is_enforced(tmp_path, monkeypatch):
    pdf_path = tmp_path / "qa-page-limit.pdf"
    pdf_path.write_bytes(make_test_pdf("page limit test"))
    monkeypatch.setattr(settings, "MAX_PDF_PAGES", 0)

    manager = object.__new__(DocumentManager)
    with pytest.raises(ValueError, match="maximum allowed pages"):
        manager._extract_pdf(pdf_path)


def test_chunking_covers_text_and_keeps_overlap(monkeypatch):
    monkeypatch.setattr(settings, "CHUNK_SIZE", 60)
    monkeypatch.setattr(settings, "CHUNK_OVERLAP", 12)
    source = " ".join(f"qa-token-{index:03}" for index in range(30))
    manager = object.__new__(DocumentManager)

    chunks = manager._chunk_text(source)

    assert len(chunks) > 1
    assert all(len(chunk) <= settings.CHUNK_SIZE + 1 for chunk in chunks)
    assert all(f"qa-token-{index:03}" in " ".join(chunks) for index in range(30))
    for previous, current in zip(chunks, chunks[1:]):
        assert set(previous.split()) & set(current.split())

    long_word = "x" * 160
    assert "".join(manager._chunk_text(long_word)) == long_word


def test_empty_text_produces_no_chunks():
    manager = object.__new__(DocumentManager)
    assert manager._chunk_text(" \n\n ") == []


def _uploaded_pdf(client, project_id: str, notebook_id: str, filename: str, content: bytes):
    return client.post(
        f"/api/racks/{project_id}/notebooks/{notebook_id}/upload",
        files={"file": (filename, content, "application/pdf")},
    )


def _database_snapshot(engine, project_id: str, notebook_id: str, embedding: list[float]):
    async def fetch():
        async with engine.connect() as connection:
            count = await connection.scalar(
                text(
                    """
                    SELECT count(*) FROM document_chunks
                    WHERE project_id = :project_id
                      AND notebook_id = :notebook_id
                    """
                ),
                {"project_id": project_id, "notebook_id": notebook_id},
            )
            results = await connection.execute(
                text(
                    """
                    SELECT content, filename, notebook_id,
                           embedding <=> :embedding AS distance
                    FROM document_chunks
                    WHERE project_id = :project_id
                      AND notebook_id = :notebook_id
                      AND embedding IS NOT NULL
                    ORDER BY embedding <=> :embedding
                    LIMIT 5
                    """
                ),
                {
                    "project_id": project_id,
                    "notebook_id": notebook_id,
                    "embedding": embedding,
                },
            )
            return int(count or 0), [dict(row) for row in results.mappings()]

    return asyncio.run(fetch())


def _project_row_counts(engine, project_id: str):
    async def fetch():
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT
                        (SELECT count(*) FROM projects WHERE id = :project_id) AS projects,
                        (SELECT count(*) FROM notebooks WHERE project_id = :project_id) AS notebooks,
                        (SELECT count(*) FROM document_chunks WHERE project_id = :project_id) AS chunks
                    """
                ),
                {"project_id": project_id},
            )
            return dict(result.mappings().one())

    return asyncio.run(fetch())


@pytest.mark.neon_e2e
def test_neon_pdf_upload_vector_search_idempotency_and_cleanup():
    """Exercise Neon end-to-end only when explicitly enabled for a test database."""
    if os.getenv("PDF_VOICE_AI_RUN_NEON_E2E") != "1":
        pytest.skip("Set PDF_VOICE_AI_RUN_NEON_E2E=1 to run against Neon.")
    if not settings.DATABASE_URL.strip():
        pytest.skip("DATABASE_URL is not configured.")

    from app.documents.manager import DocumentManager
    from app.racks.manager import RackManager
    from app.templates.generator import ProjectGenerator

    main = importlib.import_module("app.main")
    RackManager._instance = None
    DocumentManager._instance = None
    main.rack_manager = RackManager()
    main.doc_manager = DocumentManager()
    main.project_generator = ProjectGenerator(main.rack_manager, main.doc_manager)

    project_id = None
    engine = None
    with TestClient(main.app) as client:
        try:
            baseline = client.get("/api/health")
            assert baseline.status_code == 200

            marker = uuid.uuid4().hex[:12].upper()
            filename = f"qa-neon-{marker}.pdf"
            query = f"QA-NEON-RETRIEVAL-{marker}"
            pdf_text = (
                f"Automated Neon QA record. Retrieval marker {query}. "
                "This record belongs only to the temporary quality test."
            )
            pdf = make_test_pdf(pdf_text)

            created = client.post(
                "/api/racks",
                json={
                    "name": f"QA Neon PDF {marker}",
                    "description": "Temporary end-to-end quality check.",
                },
            )
            assert created.status_code == 201, created.text
            project_id = created.json()["id"]
            assert created.json()["name"] == f"QA Neon PDF {marker}"

            notebook = client.post(
                f"/api/racks/{project_id}/notebooks",
                json={"name": f"QA Notebook {marker}", "description": "Temporary."},
            )
            assert notebook.status_code == 201, notebook.text
            notebook_id = notebook.json()["id"]

            isolated_notebook = client.post(
                f"/api/racks/{project_id}/notebooks",
                json={"name": f"Isolation {marker}"},
            )
            assert isolated_notebook.status_code == 201, isolated_notebook.text
            isolated_notebook_id = isolated_notebook.json()["id"]

            unsupported = client.post(
                f"/api/racks/{project_id}/notebooks/{notebook_id}/upload",
                files={"file": ("unsupported.exe", b"not a document", "application/octet-stream")},
            )
            assert unsupported.status_code == 400

            empty_pdf = _uploaded_pdf(
                client,
                project_id,
                notebook_id,
                f"empty-{marker}.pdf",
                make_test_pdf(""),
            )
            assert empty_pdf.status_code == 400

            uploaded = _uploaded_pdf(client, project_id, notebook_id, filename, pdf)
            assert uploaded.status_code == 200, uploaded.text
            assert uploaded.json()["success"] is True
            assert uploaded.json()["pages"] == 1
            assert uploaded.json()["chunks"] > 0

            duplicate = _uploaded_pdf(client, project_id, notebook_id, filename, pdf)
            assert duplicate.status_code == 200, duplicate.text

            query_embedding = (
                main.doc_manager.embedder.encode([query], show_progress_bar=False)
                .tolist()[0]
            )
            engine = create_async_engine(
                _to_async_url(settings.DATABASE_URL),
                poolclass=NullPool,
                pool_pre_ping=True,
            )
            event.listen(engine.sync_engine, "connect", _register_vector_codec)
            chunk_count, hits = _database_snapshot(
                engine,
                project_id,
                notebook_id,
                query_embedding,
            )

            assert chunk_count == uploaded.json()["chunks"]
            assert hits, "Expected a pgvector match for the uploaded PDF."
            assert any(query in hit["content"] for hit in hits)
            assert all(hit["filename"] == filename for hit in hits)
            assert all(hit["notebook_id"] == notebook_id for hit in hits)
            assert all(math.isfinite(float(hit["distance"])) for hit in hits)
            assert min(float(hit["distance"]) for hit in hits) < 0.5

            isolated_count, isolated_hits = _database_snapshot(
                engine,
                project_id,
                isolated_notebook_id,
                query_embedding,
            )
            assert isolated_count == 0
            assert isolated_hits == []

            deleted_project_id = project_id
            deleted = client.delete(f"/api/racks/{project_id}")
            assert deleted.status_code == 200, deleted.text
            missing = client.get(f"/api/racks/{deleted_project_id}")
            assert missing.status_code == 404
            remaining_projects = client.get("/api/racks")
            assert remaining_projects.status_code == 200
            assert deleted_project_id not in {
                rack["id"] for rack in remaining_projects.json()
            }
            assert _project_row_counts(engine, deleted_project_id) == {
                "projects": 0,
                "notebooks": 0,
                "chunks": 0,
            }
            project_id = None
        finally:
            if project_id is not None:
                cleanup = client.delete(f"/api/racks/{project_id}")
                assert cleanup.status_code in {200, 404}, cleanup.text
            if engine is not None:
                asyncio.run(engine.dispose())

    RackManager._instance = None
    DocumentManager._instance = None
