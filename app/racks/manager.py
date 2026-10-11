"""Rack (Project) + Notebook manager. Only Neon/pgvector (no JSON, no ChromaDB)."""
from __future__ import annotations

import logging
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import session as db_session

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower())
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text[:48] or uuid.uuid4().hex[:12]


class RackManager:
    """Only Neon/pgvector persistence (no JSON fallback, no ChromaDB)."""

    _instance: Optional["RackManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        logger.info("RackManager initialized (Neon-only mode)")

    async def initialize_async(self) -> None:
        async with db_session() as db:
            migrated = await db.scalar(
                text("SELECT value FROM app_metadata WHERE key = 'local_projects_migrated'")
            )
            if not migrated:
                # No local JSON data to migrate; Neon is authoritative
                await db.execute(
                    text(
                        "INSERT INTO app_metadata (key, value) VALUES ('local_projects_migrated', 'true') ON CONFLICT (key) DO NOTHING"
                    )
                )

    async def list_racks_async(self) -> list[dict]:
        async with db_session() as db:
            return await self._fetch_neon_racks(db)

    async def get_async(self, rack_id: str) -> Optional[dict]:
        async with db_session() as db:
            racks = await self._fetch_neon_racks(db, rack_id)
            return racks[0] if racks else None

    async def create_async(
        self,
        name: str,
        description: str = "",
        system_instruction: str = "",
        operating_instruction: str = "",
        icon: str = "📦",
        rack_id: Optional[str] = None,
    ) -> dict:
        base_id = rack_id or _slugify(name)
        async with db_session() as db:
            rack_id = base_id
            counter = 1
            while await db.scalar(
                text("SELECT EXISTS (SELECT 1 FROM projects WHERE id = :id)"),
                {"id": rack_id},
            ):
                rack_id = f"{base_id}-{counter}"
                counter += 1
            now = datetime.now(timezone.utc)
            await db.execute(
                text(
                    "INSERT INTO projects (id, name, description, icon, system_instruction, operating_instruction, created_at, updated_at) VALUES (:id, :name, :description, :icon, :system_instruction, :operating_instruction, :created_at, :updated_at)"
                ),
                {
                    "id": rack_id,
                    "name": name.strip(),
                    "description": description.strip(),
                    "icon": icon or "📦",
                    "system_instruction": system_instruction.strip() or "Eres un asistente experto. Responde basándote únicamente en el contexto de los documentos proporcionados.",
                    "operating_instruction": operating_instruction.strip(),
                    "created_at": now,
                    "updated_at": now,
                },
            )
            return (await self._fetch_neon_racks(db, rack_id))[0]

    async def update_async(self, rack_id: str, **fields) -> Optional[dict]:
        allowed = {"name", "description", "system_instruction", "operating_instruction", "icon"}
        updates = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in fields.items()
            if key in allowed and value is not None
        }
        async with db_session() as db:
            existing = await self._fetch_neon_racks(db, rack_id)
            if not existing:
                return None
            if updates:
                updates["updated_at"] = datetime.now(timezone.utc)
                updates["rack_id"] = rack_id
                assignments = ", ".join(f"{key} = :{key}" for key in updates if key != "rack_id")
                await db.execute(
                    text(f"UPDATE projects SET {assignments} WHERE id = :rack_id"),
                    updates,
                )
            return (await self._fetch_neon_racks(db, rack_id))[0]

    async def delete_async(self, rack_id: str) -> bool:
        async with db_session() as db:
            result = await db.execute(
                text("DELETE FROM projects WHERE id = :id RETURNING id"),
                {"id": rack_id},
            )
            return result.first() is not None

    async def list_notebooks_async(self, rack_id: str) -> list[dict]:
        rack = await self.get_async(rack_id)
        return rack["notebooks"] if rack else []

    async def get_notebook_async(self, rack_id: str, notebook_id: str) -> Optional[dict]:
        rack = await self.get_async(rack_id)
        if not rack:
            return None
        return next(
            (nb for nb in rack["notebooks"] if nb["id"] == notebook_id),
            None,
        )

    async def create_notebook_async(
        self,
        rack_id: str,
        name: str,
        description: str = "",
        domain: str = "",
        notebook_id: Optional[str] = None,
    ) -> Optional[dict]:
        async with db_session() as db:
            exists = await db.scalar(
                text("SELECT EXISTS (SELECT 1 FROM projects WHERE id = :id)"),
                {"id": rack_id},
            )
            if not exists:
                return None
            base_id = notebook_id or _slugify(name)
            candidate = base_id
            counter = 1
            while await db.scalar(
                text("SELECT EXISTS (SELECT 1 FROM notebooks WHERE project_id = :project_id AND id = :id)"),
                {"project_id": rack_id, "id": candidate},
            ):
                candidate = f"{base_id}-{counter}"
                counter += 1
            now = datetime.now(timezone.utc)
            result = await db.execute(
                text(
                    "INSERT INTO notebooks (id, project_id, name, description, domain, created_at, updated_at) VALUES (:id, :project_id, :name, :description, :domain, :created_at, :updated_at) RETURNING *"
                ),
                {
                    "id": candidate,
                    "project_id": rack_id,
                    "name": name.strip(),
                    "description": description.strip(),
                    "domain": domain.strip(),
                    "created_at": now,
                    "updated_at": now,
                },
            )
            await db.execute(
                text("UPDATE projects SET updated_at = :updated_at WHERE id = :id"),
                {"updated_at": now, "id": rack_id},
            )
            row = result.mappings().one()
            return {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "domain": row["domain"],
                "created_at": _format_datetime(row["created_at"]),
                "updated_at": _format_datetime(row["updated_at"]),
            }

    async def update_notebook_async(self, rack_id: str, notebook_id: str, **fields) -> Optional[dict]:
        allowed = {"name", "description", "domain"}
        updates = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in fields.items()
            if key in allowed and value is not None
        }
        async with db_session() as db:
            result = await db.execute(
                text(
                    "SELECT id FROM notebooks WHERE project_id = :rack_id AND id = :notebook_id"
                ),
                {"rack_id": rack_id, "notebook_id": notebook_id},
            )
            if not result.first():
                return None
            if updates:
                now = datetime.now(timezone.utc)
                updates.update(rack_id=rack_id, notebook_id=notebook_id, updated_at=now)
                assignments = ", ".join(
                    f"{key} = :{key}" for key in updates
                    if key not in {"rack_id", "notebook_id"}
                )
                await db.execute(
                    text(f"UPDATE notebooks SET {assignments} WHERE project_id = :rack_id AND id = :notebook_id"),
                    updates,
                )
                await db.execute(
                    text("UPDATE projects SET updated_at = :updated_at WHERE id = :id"),
                    {"updated_at": now, "id": rack_id},
                )
            result = await db.execute(
                text(
                    "SELECT id, name, description, domain, created_at, updated_at FROM notebooks WHERE project_id = :rack_id AND id = :notebook_id"
                ),
                {"rack_id": rack_id, "notebook_id": notebook_id},
            )
            row = result.mappings().one()
            return {
                "id": row["id"],
                "name": row["name"],
                "description": row["description"],
                "domain": row["domain"],
                "created_at": _format_datetime(row["created_at"]),
                "updated_at": _format_datetime(row["updated_at"]),
            }

    async def delete_notebook_async(self, rack_id: str, notebook_id: str) -> bool:
        async with db_session() as db:
            result = await db.execute(
                text(
                    "DELETE FROM notebooks WHERE project_id = :rack_id AND id = :notebook_id RETURNING id"
                ),
                {"rack_id": rack_id, "notebook_id": notebook_id},
            )
            if result.first() is None:
                return False
            await db.execute(
                text("UPDATE projects SET updated_at = :updated_at WHERE id = :id"),
                {"updated_at": datetime.now(timezone.utc), "id": rack_id},
            )
            return True

    async def notebook_catalog_text_async(self, rack_id: str) -> str:
        notebooks = await self.list_notebooks_async(rack_id)
        if not notebooks:
            return "Este proyecto aún no tiene cuadernos."
        lines = []
        for notebook in notebooks:
            domain = f" (dominio: {notebook['domain']})" if notebook.get("domain") else ""
            description = f" – {notebook['description']}" if notebook.get("description") else ""
            lines.append(f"- Cuaderno '{notebook['name']}'{domain}{description}")
        return "\n".join(lines)

    async def _fetch_neon_racks(self, db: AsyncSession, rack_id: Optional[str] = None) -> list[dict]:
        query = """
            SELECT p.id AS project_id, p.name AS project_name,
            p.description AS project_description, p.icon AS project_icon,
            p.system_instruction, p.operating_instruction,
            p.created_at AS project_created_at, p.updated_at AS project_updated_at,
            n.id AS notebook_id, n.name AS notebook_name,
            n.description AS notebook_description, n.domain AS notebook_domain,
            n.created_at AS notebook_created_at, n.updated_at AS notebook_updated_at
            FROM projects p
            LEFT JOIN notebooks n ON n.project_id = p.id
        """
        params = {}
        if rack_id is not None:
            query += " WHERE p.id = :rack_id"
            params["rack_id"] = rack_id
        query += " ORDER BY p.name, p.id, n.created_at, n.id"
        result = await db.execute(text(query), params)
        racks_by_id: dict[str, dict] = {}
        for row in result.mappings():
            project_id = row["project_id"]
            rack = racks_by_id.setdefault(
                project_id,
                {
                    "id": project_id,
                    "name": row["project_name"],
                    "description": row["project_description"],
                    "icon": row["project_icon"],
                    "system_instruction": row["system_instruction"],
                    "operating_instruction": row["operating_instruction"],
                    "created_at": _format_datetime(row["project_created_at"]),
                    "updated_at": _format_datetime(row["project_updated_at"]),
                    "notebooks": [],
                },
            )
            if row["notebook_id"] is not None:
                rack["notebooks"].append(
                    {
                        "id": row["notebook_id"],
                        "name": row["notebook_name"],
                        "description": row["notebook_description"],
                        "domain": row["notebook_domain"],
                        "created_at": _format_datetime(row["notebook_created_at"]),
                        "updated_at": _format_datetime(row["notebook_updated_at"]),
                    }
                )
        return list(racks_by_id.values())


def _format_datetime(value) -> str:
    return value.isoformat() if isinstance(value, datetime) else value
