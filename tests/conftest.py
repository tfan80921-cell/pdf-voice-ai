"""
Shared pytest configuration for the test suite.

The application is Neon-only: every endpoint goes through ``db_session()``.
TestClient must be used as a context manager so the FastAPI lifespan runs and
``init_db()`` creates the engine, otherwise every DB-touching test fails with
``RuntimeError: DB not initialized``.

Note: endpoint tests therefore run against the database configured in the
environment (DATABASE_URL). Use a disposable database for the suite.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """TestClient that runs the FastAPI lifespan, so init_db() executes."""
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
