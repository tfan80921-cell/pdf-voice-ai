"""
Document ingestion + semantic search on Neon (pgvector).
Embedding model: same sentence-transformers as Chroma path (384-dim).
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
from app.db import session

logger = logging.getLogger(__name__)

ALLOWED_TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".log"}
ALLOWED_PDF = {".pdf"}


class NeonDocumentManager:
    _instance: Optional["NeonDocumentManager"] = None

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
        self.dim = 384

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
                text_page = page.extract_text() or ""
                if text_page.strip():
                    parts.append(f"[Página {i + 1}]\n{text_page}")
            except Exception as exc:
                logger.warning("Failed to extract page %d: %s", i + 1, exc)
        return "\n\n".join(parts), num_pages

    def _chunk_text(self, text_in: str) -> list[str]:
        text_in = re.sub(r"\n{3,}", "\n\n", text_in).strip()
        if len(text_in) <= settings.CHUNK_SIZE:
            return [text_in] if text_in else []
        chunks: list[str] = []
        start = 0
        while start < len(text_in):
            end = start + settings.CHUNK_SIZE
            if end >= len(text_in):
                chunks.append(text_in[start:].strip())
                break
            split_at = text_in.rfind("\n\n", start, end)
            if split_at == -1 or split_at <= start:
                split_at = text_in.rfind(". ", start, end)
            if split_at == -1 or split_at <= start:
                split_at = end
            chunk = text_in[start : split_at + 1].strip()
            if chunk:
                chunks.append(chunk)
            start = max(0, split_at + 1 - settings.CHUNK_OVERLAP)
        return [c for c in chunks if c]

    async def ingest_file(
        self,
        file_path: Path,
        original_filename: str,
        rack_id: str,
        notebook_id: str,
    ) -> dict:
        ext = Path(original_filename).suffix.lower()
        if ext in ALLOWED_PDF:
            full_text, num_pages = self._extract_pdf(file_path)
        elif ext in ALLOWED_TEXT_EXTENSIONS:
            full_text = file_path.read_text(encoding="utf-8", errors="replace")
            num_pages = 1
        else:
            raise ValueError(
                f"Formato no soportado: {ext}. "
                f"Aceptados: PDF, {', '.join(sorted(ALLOWED_TEXT_EXTENSIONS))}"
            )
        if not full_text.strip():
            raise ValueError("No se pudo extraer texto del archivo")

        chunks = self._chunk_text(full_text)
        if not chunks:
            raise ValueError("El fragmentado produjo cero trozos")

        doc_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()[:16]
        embeddings = self.embedder.encode(chunks, show_progress_bar=False)

        async with session() as s:
            for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                vec = emb.tolist()
                vec_lit = "[" + ",".join(str(float(x)) for x in vec) + "]"
                await s.execute(
                    text(
                        """
                        INSERT INTO document_chunks
                        (project_id, notebook_id, filename, chunk_index, content, embedding, doc_hash)
                        VALUES
                        (:pid, :nid, :fn, :idx, :content, CAST(:emb AS vector), :hash)
                        """
                    ),
                    {
                        "pid": rack_id,
                        "nid": notebook_id,
                        "fn": original_filename,
                        "idx": i,
                        "content": chunk,
                        "emb": vec_lit,
                        "hash": doc_hash,
                    },
                )

        logger.info(
            "Neon ingest '%s' -> %d chunks (project=%s notebook=%s)",
            original_filename,
            len(chunks),
            rack_id,
            notebook_id,
        )
        return {
            "filename": original_filename,
            "pages": num_pages,
            "chunks": len(chunks),
            "doc_hash": doc_hash,
            "rack_id": rack_id,
            "notebook_id": notebook_id,
        }

    async def query(
        self,
        question: str,
        rack_id: str,
        notebook_ids: Optional[list[str]] = None,
        top_k: Optional[int] = None,
    ) -> list[dict]:
        k = top_k or settings.TOP_K_RESULTS
        q_emb = self.embedder.encode([question], show_progress_bar=False)[0]
        vec_lit = "[" + ",".join(str(float(x)) for x in q_emb.tolist()) + "]"

        params: dict = {"pid": rack_id, "emb": vec_lit, "k": k}
        filter_sql = "project_id = :pid"
        if notebook_ids:
            if len(notebook_ids) == 1:
                filter_sql += " AND notebook_id = :nid0"
                params["nid0"] = notebook_ids[0]
            else:
                placeholders = []
                for i, nid in enumerate(notebook_ids):
                    key = f"nid{i}"
                    placeholders.append(f":{key}")
                    params[key] = nid
                filter_sql += f" AND notebook_id IN ({', '.join(placeholders)})"

        sql = f"""
            SELECT content, filename, notebook_id, chunk_index,
                   embedding <=> CAST(:emb AS vector) AS distance
            FROM document_chunks
            WHERE {filter_sql}
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :k
        """
        async with session() as s:
            result = await s.execute(text(sql), params)
            rows = result.mappings().all()

        return [
            {
                "text": r["content"],
                "metadata": {
                    "filename": r["filename"],
                    "notebook_id": r["notebook_id"],
                    "chunk_index": r["chunk_index"],
                },
                "distance": float(r["distance"]) if r["distance"] is not None else 0.0,
            }
            for r in rows
        ]

    async def get_context_string(
        self,
        question: str,
        rack_id: str,
        notebook_ids: Optional[list[str]] = None,
        top_k: Optional[int] = None,
    ) -> tuple[str, list[str], list[str]]:
        hits = await self.query(question, rack_id, notebook_ids, top_k)
        if not hits:
            return "", [], []
        context_parts = []
        sources: set[str] = set()
        nbs_used: set[str] = set()
        for h in hits:
            nb = h["metadata"].get("notebook_id", "?")
            fn = h["metadata"].get("filename", "unknown")
            context_parts.append(f"[Cuaderno: {nb} | Archivo: {fn}]\n{h['text']}")
            sources.add(fn)
            nbs_used.add(nb)
        return "\n\n---\n\n".join(context_parts), sorted(sources), sorted(nbs_used)

    async def document_count(
        self, rack_id: Optional[str] = None, notebook_id: Optional[str] = None
    ) -> int:
        async with session() as s:
            if not rack_id:
                r = await s.execute(text("SELECT COUNT(*) AS c FROM document_chunks"))
                return int(r.scalar() or 0)
            if notebook_id:
                r = await s.execute(
                    text(
                        "SELECT COUNT(*) FROM document_chunks "
                        "WHERE project_id = :pid AND notebook_id = :nid"
                    ),
                    {"pid": rack_id, "nid": notebook_id},
                )
            else:
                r = await s.execute(
                    text(
                        "SELECT COUNT(*) FROM document_chunks WHERE project_id = :pid"
                    ),
                    {"pid": rack_id},
                )
            return int(r.scalar() or 0)

    async def delete_rack_collection(self, rack_id: str) -> None:
        async with session() as s:
            await s.execute(
                text("DELETE FROM document_chunks WHERE project_id = :pid"),
                {"pid": rack_id},
            )

    async def clear_notebook(self, rack_id: str, notebook_id: str) -> int:
        async with session() as s:
            result = await s.execute(
                text(
                    "DELETE FROM document_chunks "
                    "WHERE project_id = :pid AND notebook_id = :nid RETURNING id"
                ),
                {"pid": rack_id, "nid": notebook_id},
            )
            return len(result.fetchall())

    async def clear_rack(self, rack_id: str) -> None:
        await self.delete_rack_collection(rack_id)
