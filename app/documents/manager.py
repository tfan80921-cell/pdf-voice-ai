"""
Document management: PDF/text ingestion and vector retrieval.
ONLY Neon/pgvector. No ChromaDB, no local fallback.
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Optional

from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from sqlalchemy import text

from app.config import settings
from app.db import session as db_session

logger = logging.getLogger(__name__)

ALLOWED_TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".log"}
ALLOWED_PDF = {".pdf"}


class DocumentManager:
    """Only Neon/pgvector persistence (no ChromaDB, no local JSON)."""

    _instance: Optional["DocumentManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        logger.info("Loading embedding model: %s", settings.EMBEDDING_MODEL)
        self.embedder = SentenceTransformer(settings.EMBEDDING_MODEL)

    async def initialize_async(self) -> None:
        # Migration logic kept for Neon-only; no ChromaDB references
        async with db_session() as db:
            migrated = await db.scalar(
                text("SELECT value FROM app_metadata WHERE key = 'local_chunks_migrated'")
            )
            if migrated:
                return
            # If local chunks exist in previous version, migrate; else skip
            chunk_count = await db.scalar(text("SELECT count(*) FROM document_chunks"))
            if chunk_count == 0 and settings.BASE_DIR.joinpath("chroma_db").exists():
                # Note: ChromaDB directory may exist physically but is not used
                pass
            await db.execute(
                text(
                    "INSERT INTO app_metadata (key, value) VALUES ('local_chunks_migrated', 'true') ON CONFLICT (key) DO NOTHING"
                )
            )

    async def ingest_file_async(
        self, file_path: Path, original_filename: str, rack_id: str, notebook_id: str
    ) -> dict:
        ext = Path(original_filename).suffix.lower()
        if ext in ALLOWED_PDF:
            full_text, num_pages = self._extract_pdf(file_path)
        elif ext in ALLOWED_TEXT_EXTENSIONS:
            full_text = file_path.read_text(encoding="utf-8", errors="replace")
            num_pages = 1
        else:
            raise ValueError(
                f"Formato no soportado: {ext}. Aceptados: PDF, {', '.join(sorted(ALLOWED_TEXT_EXTENSIONS))}"
            )
        if not full_text.strip():
            raise ValueError("No se pudo extraer texto del archivo")
        chunks = self._chunk_text(full_text)
        if not chunks:
            raise ValueError("El fragmentado produjo cero trozos")
        doc_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()[:16]
        embeddings = self.embedder.encode(chunks, show_progress_bar=False).tolist()
        rows = [
            {
                "project_id": rack_id,
                "notebook_id": notebook_id,
                "filename": original_filename,
                "chunk_index": index,
                "content": chunk,
                "embedding": _vector_values(embedding),
                "doc_hash": doc_hash,
            }
            for index, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]
        async with db_session() as db:
            await db.execute(
                text(
                    """
                    INSERT INTO document_chunks (
                        project_id, notebook_id, filename, chunk_index,
                        content, embedding, doc_hash
                    ) VALUES (
                        :project_id, :notebook_id, :filename, :chunk_index,
                        :content, :embedding, :doc_hash
                    )
                    ON CONFLICT (project_id, notebook_id, filename, doc_hash, chunk_index)
                    DO UPDATE SET content = EXCLUDED.content, embedding = EXCLUDED.embedding
                    """
                ),
                rows,
            )
        logger.info(
            "Neon: rack '%s' / notebook '%s' <- '%s' (%d pages/parts, %d chunks)",
            rack_id, notebook_id, original_filename, num_pages, len(chunks),
        )
        return {
            "filename": original_filename,
            "pages": num_pages,
            "chunks": len(chunks),
            "doc_hash": doc_hash,
            "rack_id": rack_id,
            "notebook_id": notebook_id,
        }

    def _extract_pdf(self, file_path: Path) -> tuple[str, int]:
        reader = PdfReader(str(file_path))
        num_pages = len(reader.pages)
        if num_pages > settings.MAX_PDF_PAGES:
            raise ValueError(
                f"PDF exceeds maximum allowed pages ({settings.MAX_PDF_PAGES})"
            )
        parts: list[str] = []
        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
                if text.strip():
                    parts.append(f"[Página {i + 1}]\n{text}")
            except Exception as exc:
                logger.warning("Failed to extract page %d: %s", i + 1, exc)
        return "\n\n".join(parts), num_pages

    async def query_async(
        self,
        question: str,
        rack_id: str,
        notebook_ids: Optional[list[str]] = None,
        top_k: Optional[int] = None,
    ) -> list[dict]:
        embedding = self.embedder.encode([question], show_progress_bar=False).tolist()[0]
        params: dict = {
            "rack_id": rack_id,
            "embedding": _vector_values(embedding),
            "limit": top_k or settings.TOP_K_RESULTS,
        }
        notebook_filter = ""
        if notebook_ids:
            bind_names = []
            for index, notebook_id in enumerate(notebook_ids):
                bind_name = f"notebook_id_{index}"
                bind_names.append(f":{bind_name}")
                params[bind_name] = notebook_id
            notebook_filter = f" AND notebook_id IN ({', '.join(bind_names)})"
        async with db_session() as db:
            result = await db.execute(
                text(
                    f"""
                    SELECT content, filename, chunk_index, doc_hash, notebook_id,
                           embedding <=> :embedding AS distance
                    FROM document_chunks
                    WHERE project_id = :rack_id
                      AND embedding IS NOT NULL
                      {notebook_filter}
                    ORDER BY embedding <=> :embedding
                    LIMIT :limit
                    """
                ),
                params,
            )
            return [
                {
                    "text": row["content"],
                    "metadata": {
                        "filename": row["filename"],
                        "chunk_index": row["chunk_index"],
                        "doc_hash": row["doc_hash"],
                        "rack_id": rack_id,
                        "notebook_id": row["notebook_id"],
                    },
                    "distance": float(row["distance"]),
                }
                for row in result.mappings()
            ]

    async def get_context_string_async(
        self,
        question: str,
        rack_id: str,
        notebook_ids: Optional[list[str]] = None,
        top_k: Optional[int] = None,
    ) -> tuple[str, list[str], list[str]]:
        hits = await self.query_async(question, rack_id, notebook_ids, top_k)
        if not hits:
            return "", [], []
        context_parts = []
        sources: set[str] = set()
        notebooks_used: set[str] = set()
        for hit in hits:
            metadata = hit["metadata"]
            notebook_id = metadata.get("notebook_id", "?")
            filename = metadata.get("filename", "unknown")
            context_parts.append(f"[Cuaderno: {notebook_id} | Archivo: {filename}]\n{hit['text']}")
            sources.add(filename)
            notebooks_used.add(notebook_id)
        return (
            "\n\n---\n\n".join(context_parts),
            sorted(sources),
            sorted(notebooks_used),
        )

    async def document_count_async(
        self, rack_id: Optional[str] = None, notebook_id: Optional[str] = None
    ) -> int:
        conditions = []
        params = {}
        if rack_id is not None:
            conditions.append("project_id = :rack_id")
            params["rack_id"] = rack_id
        if notebook_id is not None:
            conditions.append("notebook_id = :notebook_id")
            params["notebook_id"] = notebook_id
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        async with db_session() as db:
            count = await db.scalar(
                text(f"SELECT count(*) FROM document_chunks{where}"),
                params,
            )
            return int(count or 0)

    async def delete_rack_collection_async(self, rack_id: str) -> None:
        async with db_session() as db:
            await db.execute(
                text("DELETE FROM document_chunks WHERE project_id = :rack_id"),
                {"rack_id": rack_id},
            )

    async def clear_notebook_async(self, rack_id: str, notebook_id: str) -> int:
        async with db_session() as db:
            result = await db.execute(
                text(
                    "DELETE FROM document_chunks WHERE project_id = :rack_id AND notebook_id = :notebook_id RETURNING id"
                ),
                {"rack_id": rack_id, "notebook_id": notebook_id},
            )
            return len(result.fetchall())

    def _chunk_text(self, text: str) -> list[str]:
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if len(text) <= settings.CHUNK_SIZE:
            return [text] if text else []
        chunks: list[str] = []
        start = 0
        while start < len(text):
            end = start + settings.CHUNK_SIZE
            if end >= len(text):
                chunks.append(text[start:].strip())
                break
            split_at = text.rfind("\n\n", start, end)
            if split_at == -1 or split_at <= start:
                split_at = text.rfind(". ", start, end)
            if split_at == -1 or split_at <= start:
                split_at = end
            chunk = text[start : split_at + 1].strip()
            if chunk:
                chunks.append(chunk)
            start = max(0, split_at + 1 - settings.CHUNK_OVERLAP)
        return [c for c in chunks if c]


def _vector_values(values) -> list[float]:
    return [float(value) for value in values]
