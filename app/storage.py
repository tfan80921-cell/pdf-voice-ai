"""
Storage backend selector: Neon (Postgres+pgvector) or local (JSON+Chroma).
All public helpers are async so main.py can always await.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from app.db import is_neon_enabled

logger = logging.getLogger(__name__)

_neon_racks = None
_neon_docs = None
_local_racks = None
_local_docs = None


def _get_local():
    global _local_racks, _local_docs
    if _local_racks is None:
        from app.racks.manager import RackManager
        from app.documents.manager import DocumentManager

        _local_racks = RackManager()
        _local_docs = DocumentManager()
    return _local_racks, _local_docs


def _get_neon():
    global _neon_racks, _neon_docs
    if _neon_racks is None:
        from app.racks.neon_manager import NeonRackManager
        from app.documents.neon_manager import NeonDocumentManager

        _neon_racks = NeonRackManager()
        _neon_docs = NeonDocumentManager()
    return _neon_racks, _neon_docs


def backend_name() -> str:
    return "neon" if is_neon_enabled() else "local"


async def list_racks() -> list[dict]:
    if is_neon_enabled():
        racks, _ = _get_neon()
        return await racks.list_racks()
    racks, _ = _get_local()
    return await asyncio.to_thread(racks.list_racks)


async def get_rack(rack_id: str) -> Optional[dict]:
    if is_neon_enabled():
        racks, _ = _get_neon()
        return await racks.get(rack_id)
    racks, _ = _get_local()
    return await asyncio.to_thread(racks.get, rack_id)


async def create_rack(**kwargs) -> dict:
    if is_neon_enabled():
        racks, _ = _get_neon()
        return await racks.create(**kwargs)
    racks, _ = _get_local()
    return await asyncio.to_thread(lambda: racks.create(**kwargs))


async def update_rack(rack_id: str, **kwargs) -> Optional[dict]:
    if is_neon_enabled():
        racks, _ = _get_neon()
        return await racks.update(rack_id, **kwargs)
    racks, _ = _get_local()
    return await asyncio.to_thread(lambda: racks.update(rack_id, **kwargs))


async def delete_rack(rack_id: str) -> bool:
    if is_neon_enabled():
        racks, docs = _get_neon()
        ok = await racks.delete(rack_id)
        if ok:
            await docs.delete_rack_collection(rack_id)
        return ok
    racks, docs = _get_local()
    ok = await asyncio.to_thread(racks.delete, rack_id)
    if ok:
        await asyncio.to_thread(docs.delete_rack_collection, rack_id)
    return ok


async def list_notebooks(rack_id: str) -> list[dict]:
    if is_neon_enabled():
        racks, _ = _get_neon()
        return await racks.list_notebooks(rack_id)
    racks, _ = _get_local()
    return await asyncio.to_thread(racks.list_notebooks, rack_id)


async def get_notebook(rack_id: str, notebook_id: str) -> Optional[dict]:
    if is_neon_enabled():
        racks, _ = _get_neon()
        return await racks.get_notebook(rack_id, notebook_id)
    racks, _ = _get_local()
    return await asyncio.to_thread(racks.get_notebook, rack_id, notebook_id)


async def create_notebook(rack_id: str, **kwargs) -> Optional[dict]:
    if is_neon_enabled():
        racks, _ = _get_neon()
        return await racks.create_notebook(rack_id, **kwargs)
    racks, _ = _get_local()
    return await asyncio.to_thread(lambda: racks.create_notebook(rack_id, **kwargs))


async def update_notebook(rack_id: str, notebook_id: str, **kwargs) -> Optional[dict]:
    if is_neon_enabled():
        racks, _ = _get_neon()
        return await racks.update_notebook(rack_id, notebook_id, **kwargs)
    racks, _ = _get_local()
    return await asyncio.to_thread(
        lambda: racks.update_notebook(rack_id, notebook_id, **kwargs)
    )


async def delete_notebook(rack_id: str, notebook_id: str) -> tuple[bool, int]:
    """Returns (ok, deleted_chunk_count)."""
    if is_neon_enabled():
        racks, docs = _get_neon()
        ok = await racks.delete_notebook(rack_id, notebook_id)
        deleted = await docs.clear_notebook(rack_id, notebook_id) if ok else 0
        return ok, deleted
    racks, docs = _get_local()
    ok = await asyncio.to_thread(racks.delete_notebook, rack_id, notebook_id)
    deleted = (
        await asyncio.to_thread(docs.clear_notebook, rack_id, notebook_id) if ok else 0
    )
    return ok, deleted


async def notebook_catalog_text(rack_id: str) -> str:
    if is_neon_enabled():
        racks, _ = _get_neon()
        return await racks.notebook_catalog_text(rack_id)
    racks, _ = _get_local()
    return await asyncio.to_thread(racks.notebook_catalog_text, rack_id)


async def ingest_file(
    file_path: Path,
    original_filename: str,
    rack_id: str,
    notebook_id: str,
) -> dict:
    if is_neon_enabled():
        _, docs = _get_neon()
        return await docs.ingest_file(
            file_path, original_filename, rack_id, notebook_id
        )
    _, docs = _get_local()
    return await asyncio.to_thread(
        docs.ingest_file, file_path, original_filename, rack_id, notebook_id
    )


async def get_context_string(
    question: str,
    rack_id: str,
    notebook_ids: Optional[list[str]] = None,
    top_k: Optional[int] = None,
) -> tuple[str, list[str], list[str]]:
    if is_neon_enabled():
        _, docs = _get_neon()
        return await docs.get_context_string(
            question, rack_id, notebook_ids, top_k
        )
    _, docs = _get_local()
    return await asyncio.to_thread(
        docs.get_context_string, question, rack_id, notebook_ids, top_k
    )


async def document_count(
    rack_id: Optional[str] = None, notebook_id: Optional[str] = None
) -> int:
    if is_neon_enabled():
        _, docs = _get_neon()
        return await docs.document_count(rack_id, notebook_id)
    _, docs = _get_local()
    return await asyncio.to_thread(docs.document_count, rack_id, notebook_id)
