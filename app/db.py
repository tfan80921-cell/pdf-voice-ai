"""
Neon / Postgres connection + schema bootstrap (pgvector).
Uses DATABASE_URL from settings. If empty, callers should fall back to local storage.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

logger = logging.getLogger(__name__)

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def is_neon_enabled() -> bool:
    return bool(settings.DATABASE_URL and settings.DATABASE_URL.strip())


def _to_async_url(url: str) -> str:
    """Normalize postgres URL for asyncpg."""
    u = url.strip()
    if u.startswith("postgres://"):
        u = "postgresql://" + u[len("postgres://") :]
    if u.startswith("postgresql://") and "+asyncpg" not in u:
        u = u.replace("postgresql://", "postgresql+asyncpg://", 1)
    return u


async def init_db() -> None:
    """Create engine, enable pgvector, create tables if missing."""
    global _engine, _session_factory
    if not is_neon_enabled():
        logger.info("DATABASE_URL not set — using local JSON + ChromaDB")
        return
    if _engine is not None:
        return

    url = _to_async_url(settings.DATABASE_URL)
    _engine = create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=settings.DEBUG,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)

    async with _engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id            TEXT PRIMARY KEY,
                    name          TEXT NOT NULL,
                    description   TEXT NOT NULL DEFAULT '',
                    icon          TEXT NOT NULL DEFAULT '📦',
                    system_instruction    TEXT NOT NULL DEFAULT '',
                    operating_instruction TEXT NOT NULL DEFAULT '',
                    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS notebooks (
                    id          TEXT PRIMARY KEY,
                    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    name        TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    domain      TEXT NOT NULL DEFAULT '',
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS document_chunks (
                    id           BIGSERIAL PRIMARY KEY,
                    project_id   TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    notebook_id  TEXT NOT NULL REFERENCES notebooks(id) ON DELETE CASCADE,
                    filename     TEXT NOT NULL,
                    chunk_index  INT NOT NULL,
                    content      TEXT NOT NULL,
                    embedding    vector(384),
                    doc_hash     TEXT NOT NULL DEFAULT '',
                    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS idx_chunks_project_notebook
                ON document_chunks (project_id, notebook_id)
                """
            )
        )
        try:
            await conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_chunks_embedding
                    ON document_chunks
                    USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 100)
                    """
                )
            )
        except Exception as exc:
            logger.warning("Vector index create skipped/deferred: %s", exc)

    logger.info("Neon/Postgres schema ready (pgvector)")


async def close_db() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


@asynccontextmanager
async def session() -> AsyncIterator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("DB not initialized — call init_db() or set DATABASE_URL")
    async with _session_factory() as s:
        try:
            yield s
            await s.commit()
        except Exception:
            await s.rollback()
            raise
