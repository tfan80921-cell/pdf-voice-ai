"""
Neon / Postgres connection + schema bootstrap (pgvector).
Uses DATABASE_URL from settings. If empty, callers should fall back to local storage.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pgvector.asyncpg import register_vector
from sqlalchemy import event, text
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
    parts = urlsplit(url.strip())
    scheme = parts.scheme
    if scheme == "postgres":
        scheme = "postgresql"
    if scheme == "postgresql":
        scheme = "postgresql+asyncpg"

    query = urlencode(
        [
            ("ssl" if key == "sslmode" else key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key != "channel_binding"
        ]
    )
    return urlunsplit(parts._replace(scheme=scheme, query=query))


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
        raw_connection = await conn.get_raw_connection()
        await register_vector(raw_connection.driver_connection)
        event.listen(_engine.sync_engine, "connect", _register_vector_codec)
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS app_metadata (
                    key   TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
        )
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
                    id          TEXT NOT NULL,
                    project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    name        TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    domain      TEXT NOT NULL DEFAULT '',
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (project_id, id)
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
                    notebook_id  TEXT NOT NULL,
                    filename     TEXT NOT NULL,
                    chunk_index  INT NOT NULL,
                    content      TEXT NOT NULL,
                    embedding    vector(384),
                    doc_hash     TEXT NOT NULL DEFAULT '',
                    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                    FOREIGN KEY (project_id, notebook_id)
                        REFERENCES notebooks(project_id, id) ON DELETE CASCADE
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
        await conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_chunks_unique_document_part
                ON document_chunks (project_id, notebook_id, filename, doc_hash, chunk_index)
                """
            )
        )
        try:
            async with conn.begin_nested():
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


def _register_vector_codec(dbapi_connection, _connection_record) -> None:
    dbapi_connection.run_async(register_vector)


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
