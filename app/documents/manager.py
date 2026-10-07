"""
Document management: PDF + text ingestion with pypdf + ChromaDB.
Documents are scoped by rack_id + notebook_id (cuaderno).
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)

ALLOWED_TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".log"}
ALLOWED_PDF = {".pdf"}


class DocumentManager:
    """
    One embedding model + one Chroma client.
    One collection per rack; documents tagged with notebook_id in metadata.
    """

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

        self.client = chromadb.PersistentClient(
            path=str(settings.CHROMA_PERSIST_DIR),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collections: dict[str, chromadb.Collection] = {}
        logger.info("ChromaDB client ready at %s", settings.CHROMA_PERSIST_DIR)

    def _collection_name(self, rack_id: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9_]", "_", rack_id)[:50]
        return f"rack_{safe}"

    def _get_collection(self, rack_id: str) -> chromadb.Collection:
        name = self._collection_name(rack_id)
        if name not in self._collections:
            self._collections[name] = self.client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine", "rack_id": rack_id},
            )
        return self._collections[name]

    def ingest_file(
        self,
        file_path: Path,
        original_filename: str,
        rack_id: str,
        notebook_id: str,
    ) -> dict:
        """Ingest PDF or plain-text file into the rack collection under a notebook."""
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

        collection = self._get_collection(rack_id)
        doc_hash = hashlib.sha256(full_text.encode("utf-8")).hexdigest()[:16]
        ids = [f"{rack_id}_{notebook_id}_{doc_hash}_{i}" for i in range(len(chunks))]
        embeddings = self.embedder.encode(chunks, show_progress_bar=False).tolist()
        metadatas = [
            {
                "filename": original_filename,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "doc_hash": doc_hash,
                "rack_id": rack_id,
                "notebook_id": notebook_id,
            }
            for i in range(len(chunks))
        ]

        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
        )

        logger.info(
            "Rack '%s' / Notebook '%s' ← '%s' (%d pages/parts, %d chunks)",
            rack_id,
            notebook_id,
            original_filename,
            num_pages,
            len(chunks),
        )
        return {
            "filename": original_filename,
            "pages": num_pages,
            "chunks": len(chunks),
            "doc_hash": doc_hash,
            "rack_id": rack_id,
            "notebook_id": notebook_id,
        }

    def ingest_pdf(
        self, file_path: Path, original_filename: str, rack_id: str, notebook_id: str = "default"
    ) -> dict:
        return self.ingest_file(file_path, original_filename, rack_id, notebook_id)

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

    def query(
        self,
        question: str,
        rack_id: str,
        notebook_ids: Optional[list[str]] = None,
        top_k: Optional[int] = None,
    ) -> list[dict]:
        collection = self._get_collection(rack_id)
        k = top_k or settings.TOP_K_RESULTS
        if collection.count() == 0:
            return []

        query_embedding = self.embedder.encode(
            [question], show_progress_bar=False
        ).tolist()

        where = None
        if notebook_ids:
            if len(notebook_ids) == 1:
                where = {"notebook_id": notebook_ids[0]}
            else:
                where = {"notebook_id": {"$in": notebook_ids}}

        kwargs: dict = {
            "query_embeddings": query_embedding,
            "n_results": min(k, collection.count()),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        try:
            results = collection.query(**kwargs)
        except Exception:
            results = collection.query(
                query_embeddings=query_embedding,
                n_results=min(k, collection.count()),
                include=["documents", "metadatas", "distances"],
            )

        hits: list[dict] = []
        if results and results["documents"]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                if notebook_ids and meta.get("notebook_id") not in notebook_ids:
                    continue
                hits.append({"text": doc, "metadata": meta, "distance": dist})
        return hits

    def get_context_string(
        self,
        question: str,
        rack_id: str,
        notebook_ids: Optional[list[str]] = None,
        top_k: Optional[int] = None,
    ) -> tuple[str, list[str], list[str]]:
        hits = self.query(question, rack_id, notebook_ids, top_k)
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

    def document_count(
        self, rack_id: Optional[str] = None, notebook_id: Optional[str] = None
    ) -> int:
        if not rack_id:
            total = 0
            for col in self.client.list_collections():
                if col.name.startswith("rack_"):
                    total += col.count()
            return total

        collection = self._get_collection(rack_id)
        if not notebook_id:
            return collection.count()

        try:
            result = collection.get(
                where={"notebook_id": notebook_id},
                include=[],
            )
            return len(result["ids"]) if result and result["ids"] else 0
        except Exception:
            return 0

    def delete_rack_collection(self, rack_id: str) -> None:
        name = self._collection_name(rack_id)
        try:
            self.client.delete_collection(name)
            self._collections.pop(name, None)
        except Exception:
            pass

    def clear_notebook(self, rack_id: str, notebook_id: str) -> int:
        collection = self._get_collection(rack_id)
        try:
            result = collection.get(where={"notebook_id": notebook_id}, include=[])
            ids = result["ids"] if result else []
            if ids:
                collection.delete(ids=ids)
            return len(ids)
        except Exception as exc:
            logger.warning("clear_notebook failed: %s", exc)
            return 0

    def clear_rack(self, rack_id: str) -> None:
        name = self._collection_name(rack_id)
        try:
            self.client.delete_collection(name)
        except Exception:
            pass
        self._collections.pop(name, None)
        self._get_collection(rack_id)

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
