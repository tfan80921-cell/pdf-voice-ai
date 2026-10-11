"""
Project + Notebook CRUD on Neon Postgres.
Same public shape as RackManager (dicts) for drop-in use from main.py.
"""
from __future__ import annotations

import logging
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text

from app.db import session

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _slugify(text_in: str) -> str:
    t = unicodedata.normalize("NFKD", text_in).encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"[^\w\s-]", "", t.lower())
    t = re.sub(r"[-\s]+", "-", t).strip("-")
    return t[:48] or uuid.uuid4().hex[:12]


def _row_project(r, notebooks: list | None = None) -> dict:
    return {
        "id": r["id"],
        "name": r["name"],
        "description": r["description"] or "",
        "icon": r["icon"] or "\U0001f4e6",
        "system_instruction": r["system_instruction"] or "",
        "operating_instruction": r["operating_instruction"] or "",
        "created_at": r["created_at"].isoformat() if r["created_at"] else "",
        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else "",
        "notebooks": notebooks if notebooks is not None else [],
    }


def _row_notebook(r) -> dict:
    return {
        "id": r["id"],
        "name": r["name"],
        "description": r["description"] or "",
        "domain": r["domain"] or "",
        "created_at": r["created_at"].isoformat() if r["created_at"] else "",
        "updated_at": r["updated_at"].isoformat() if r["updated_at"] else "",
    }


class NeonRackManager:
    """Async-capable manager; methods are async."""

    async def list_racks(self) -> list[dict]:
        async with session() as s:
            result = await s.execute(
                text("SELECT * FROM projects ORDER BY name")
            )
            projects = result.mappings().all()
            out = []
            for p in projects:
                nbs = await self._notebooks_for(s, p["id"])
                out.append(_row_project(p, nbs))
            return out

    async def get(self, rack_id: str) -> Optional[dict]:
        async with session() as s:
            result = await s.execute(
                text("SELECT * FROM projects WHERE id = :id"),
                {"id": rack_id},
            )
            p = result.mappings().first()
            if not p:
                return None
            nbs = await self._notebooks_for(s, rack_id)
            return _row_project(p, nbs)

    async def create(
        self,
        name: str,
        description: str = "",
        system_instruction: str = "",
        operating_instruction: str = "",
        icon: str = "\U0001f4e6",
        rack_id: Optional[str] = None,
    ) -> dict:
        rid = rack_id or _slugify(name)
        async with session() as s:
            base, counter = rid, 1
            while True:
                exists = await s.execute(
                    text("SELECT 1 FROM projects WHERE id = :id"), {"id": rid}
                )
                if not exists.first():
                    break
                rid = f"{base}-{counter}"
                counter += 1

            now = _now()
            default_sys = (
                system_instruction.strip()
                or "Eres un asistente experto. Responde basándote únicamente en el contexto de los documentos proporcionados."
            )
            await s.execute(
                text(
                    """
                    INSERT INTO projects
                    (id, name, description, icon, system_instruction, operating_instruction, created_at, updated_at)
                    VALUES
                    (:id, :name, :description, :icon, :sys, :op, :created, :updated)
                    """
                ),
                {
                    "id": rid,
                    "name": name.strip(),
                    "description": description.strip(),
                    "icon": icon or "\U0001f4e6",
                    "sys": default_sys,
                    "op": operating_instruction.strip(),
                    "created": now,
                    "updated": now,
                },
            )
        return await self.get(rid)  # type: ignore

    async def update(self, rack_id: str, **fields) -> Optional[dict]:
        allowed = {
            "name",
            "description",
            "system_instruction",
            "operating_instruction",
            "icon",
        }
        sets = []
        params: dict = {"id": rack_id, "updated": _now()}
        for k, v in fields.items():
            if k in allowed and v is not None:
                sets.append(f"{k} = :{k}")
                params[k] = v.strip() if isinstance(v, str) else v
        if not sets:
            return await self.get(rack_id)
        sets.append("updated_at = :updated")
        async with session() as s:
            result = await s.execute(
                text(f"UPDATE projects SET {', '.join(sets)} WHERE id = :id RETURNING id"),
                params,
            )
            if not result.first():
                return None
        return await self.get(rack_id)

    async def delete(self, rack_id: str) -> bool:
        async with session() as s:
            result = await s.execute(
                text("DELETE FROM projects WHERE id = :id RETURNING id"),
                {"id": rack_id},
            )
            return result.first() is not None

    async def list_notebooks(self, rack_id: str) -> list[dict]:
        async with session() as s:
            return await self._notebooks_for(s, rack_id)

    async def get_notebook(self, rack_id: str, notebook_id: str) -> Optional[dict]:
        async with session() as s:
            result = await s.execute(
                text(
                    "SELECT * FROM notebooks WHERE id = :nid AND project_id = :pid"
                ),
                {"nid": notebook_id, "pid": rack_id},
            )
            r = result.mappings().first()
            return _row_notebook(r) if r else None

    async def create_notebook(
        self,
        rack_id: str,
        name: str,
        description: str = "",
        domain: str = "",
        notebook_id: Optional[str] = None,
    ) -> Optional[dict]:
        if not await self.get(rack_id):
            return None
        nid = notebook_id or _slugify(name)
        async with session() as s:
            base, counter = nid, 1
            while True:
                exists = await s.execute(
                    text(
                        "SELECT 1 FROM notebooks WHERE id = :id AND project_id = :pid"
                    ),
                    {"id": nid, "pid": rack_id},
                )
                if not exists.first():
                    break
                nid = f"{base}-{counter}"
                counter += 1
            now = _now()
            await s.execute(
                text(
                    """
                    INSERT INTO notebooks
                    (id, project_id, name, description, domain, created_at, updated_at)
                    VALUES
                    (:id, :pid, :name, :description, :domain, :created, :updated)
                    """
                ),
                {
                    "id": nid,
                    "pid": rack_id,
                    "name": name.strip(),
                    "description": description.strip(),
                    "domain": domain.strip(),
                    "created": now,
                    "updated": now,
                },
            )
            await s.execute(
                text("UPDATE projects SET updated_at = :u WHERE id = :pid"),
                {"u": now, "pid": rack_id},
            )
        return await self.get_notebook(rack_id, nid)

    async def update_notebook(
        self, rack_id: str, notebook_id: str, **fields
    ) -> Optional[dict]:
        allowed = {"name", "description", "domain"}
        sets = []
        params: dict = {"nid": notebook_id, "pid": rack_id, "updated": _now()}
        for k, v in fields.items():
            if k in allowed and v is not None:
                sets.append(f"{k} = :{k}")
                params[k] = v.strip() if isinstance(v, str) else v
        if not sets:
            return await self.get_notebook(rack_id, notebook_id)
        sets.append("updated_at = :updated")
        async with session() as s:
            result = await s.execute(
                text(
                    f"UPDATE notebooks SET {', '.join(sets)} "
                    "WHERE id = :nid AND project_id = :pid RETURNING id"
                ),
                params,
            )
            if not result.first():
                return None
            await s.execute(
                text("UPDATE projects SET updated_at = :u WHERE id = :pid"),
                {"u": params["updated"], "pid": rack_id},
            )
        return await self.get_notebook(rack_id, notebook_id)

    async def delete_notebook(self, rack_id: str, notebook_id: str) -> bool:
        async with session() as s:
            result = await s.execute(
                text(
                    "DELETE FROM notebooks WHERE id = :nid AND project_id = :pid RETURNING id"
                ),
                {"nid": notebook_id, "pid": rack_id},
            )
            ok = result.first() is not None
            if ok:
                await s.execute(
                    text("UPDATE projects SET updated_at = :u WHERE id = :pid"),
                    {"u": _now(), "pid": rack_id},
                )
            return ok

    async def notebook_catalog_text(self, rack_id: str) -> str:
        notebooks = await self.list_notebooks(rack_id)
        if not notebooks:
            return "Este proyecto aún no tiene cuadernos."
        lines = []
        for nb in notebooks:
            domain = f" (dominio: {nb['domain']})" if nb.get("domain") else ""
            desc = f" – {nb['description']}" if nb.get("description") else ""
            lines.append(f"- Cuaderno '{nb['name']}'{domain}{desc}")
        return "\n".join(lines)

    async def _notebooks_for(self, s, rack_id: str) -> list[dict]:
        result = await s.execute(
            text(
                "SELECT * FROM notebooks WHERE project_id = :pid ORDER BY name"
            ),
            {"pid": rack_id},
        )
        return [_row_notebook(r) for r in result.mappings().all()]
