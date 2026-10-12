"""Shared fixtures for explicitly enabled Neon endpoint and retrieval tests."""
import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Use a configured Neon database only when the operator opts into live QA."""
    from app.config import settings

    if os.getenv("PDF_VOICE_AI_RUN_NEON_E2E") != "1":
        pytest.skip("Set PDF_VOICE_AI_RUN_NEON_E2E=1 to run Neon integration tests.")
    if not settings.DATABASE_URL.strip():
        pytest.skip("DATABASE_URL is not configured.")

    from app.main import app

    app.state.limiter.enabled = False
    with TestClient(app) as test_client:
        yield test_client
